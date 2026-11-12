"""Native MongoDB and AsterixDB adapters; bounded streaming restores."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import socket
import struct
import time

import requests
from engines import identifier, source_rows
from document_runtime import activate
from protocol import result_signature
from umbra_runtime import docker


class MongoDB:
    def __init__(self,system,config,namespace,threads,cpus):
        self.system=system
        import bsonjs
        from pymongo import MongoClient
        self.config,self.namespace,self.bsonjs=config,identifier(namespace),bsonjs
        self.meta=activate(system,config,cpus)
        self.client=MongoClient(config['url'],serverSelectionTimeoutMS=30000,
                            appname='specson-formal',w=1,journal=True)
        cache=self.client.admin.command('serverStatus')['wiredTiger']['cache']['maximum bytes configured']
        if cache!=config['cache_gib']*1024**3:
            raise RuntimeError('MongoDB WiredTiger cache mismatch')
        self.meta.update(version=self.client.server_info()['version'],wiredtiger_cache_bytes=cache,
            collection_block_compressor=config.get('block_compressor','snappy'),
            query_parallelism='native standalone query; CPU budget is not a forced parallel scan',
            write_concern={'w':1,'j':True},restore_encoding='native libbson relaxed Extended JSON')

    def collection(self,table):
        namespace,stem=map(identifier,table.split('.'))
        if namespace!=self.namespace:
            raise ValueError('Unexpected database namespace')
        return self.client[namespace+'__'+stem]['documents']

    def command(self,statement):
        request=json.loads(statement)
        if 'create' in request:
            col=self.collection(request['create'])
            compressor=self.config.get('block_compressor','snappy')
            result=col.database.create_collection(col.name,storageEngine={
                'wiredTiger':{'configString':'block_compressor='+compressor}})
            actual=self.storage(request['create'])['block_compressor']
            if actual!=compressor:
                raise RuntimeError('MongoDB collection block compressor mismatch: '+str(actual))
            return result
        raise ValueError('Unknown MongoDB management command')

    def exists(self,table):
        col=self.collection(table)
        return col.name in col.database.list_collection_names()

    def register(self,schema):
        return None

    def ingest(self,table,files,schema_id,replace_nul=False):
        from bson.raw_bson import RawBSONDocument
        col=self.collection(table)
        batch=[];size=0
        for ident,text in source_rows(files,replace_nul):
            envelope=(b'{"_id":'+str(ident).encode()+b',"doc_id":'+str(ident).encode()+
                      b',"doc":'+text+b'}')
            raw=self.bsonjs.loads(envelope)
            batch.append(RawBSONDocument(raw));size+=len(raw)
            if size>=8*1024**2 or len(batch)>=10000:
                col.insert_many(batch,ordered=False);batch=[];size=0
        if batch:
            col.insert_many(batch,ordered=False)

    def validate(self,table,expected):
        col=self.collection(table)
        summary=list(col.aggregate([{'$group':{'_id':None,'n':{'$sum':1},
            'lo':{'$min':'$doc_id'},'hi':{'$max':'$doc_id'}}}]))
        if summary!=[{'_id':None,'n':expected,'lo':0,'hi':expected-1}]:
            raise RuntimeError('MongoDB row/doc_id validation failed: '+str(summary))

    def maintain(self,table):
        self.client.admin.command('fsync')

    def storage(self,table):
        col=self.collection(table)
        stats=col.database.command('collStats',col.name)
        compressor=re.search(r'(?:^|,)block_compressor=([^,]+)',stats['wiredTiger']['creationString'])
        return dict(disk_bytes=stats['storageSize']+stats['totalIndexSize'],
            scope='MongoDB allocated collection + index files; excludes shared journal/metadata',
            data_bytes=stats['storageSize'],index_bytes=stats['totalIndexSize'],
            logical_data_bytes=stats['size'],block_compressor=compressor.group(1) if compressor else None,
            indexes=list(col.list_indexes()))

    def drop(self,table):
        col=self.collection(table);name=col.database.name
        self.client.drop_database(name)
        self.client.admin.command('fsync')
        # directoryPerDB gives this dataset owned physical files, not just free
        # pages inside a shared collection. WiredTiger may finish drops later.
        deadline=time.monotonic()+120
        while True:
            present=docker('exec',self.config['container'],'sh','-c',
                           'test ! -d "$1" || find "$1" -type f', 'sh','/data/'+name)
            if not present:
                break
            if time.monotonic()>=deadline:
                raise RuntimeError('MongoDB dataset files remain after dropDatabase')
            time.sleep(.2)
        return dict(cleaned=True,method='isolated dropDatabase; data/index file removal verified')

    def prepare(self,statement,streaming=False):
        request=json.loads(statement)
        return self.collection(request['collection']),request,streaming

    def receive(self,prepared):
        col,request,streaming=prepared
        if not streaming:
            return list(col.aggregate_raw_batches(request['pipeline'],allowDiskUse=True,batchSize=10000))
        rows=0;output_bytes=0
        for batch in col.find_raw_batches({}, {'_id':0,'doc':1},batch_size=2048):
            at=0
            while at<len(batch):
                length=struct.unpack_from('<i',batch,at)[0]
                # Projection emits exactly one embedded document field. The
                # BSON subdocument is converted by libbson, without Python JSON
                # parsing or visiting every value in Python.
                if batch[at+4:at+9]!=b'\x03doc\x00':
                    raise RuntimeError('Unexpected MongoDB restore projection')
                text=self.bsonjs.dumps(batch[at+9:at+length-1])
                output_bytes+=len(text);rows+=1;at+=length
        return dict(result_rows=rows,json_characters=output_bytes)

    def finish(self,result):
        if isinstance(result,dict):
            return result
        if getattr(self,'verify_results',False):
            import bson
            signature=result_signature(row for batch in result for row in bson.decode_all(batch))
            return dict(result_rows=signature['rows'],result_signature=signature)
        count=0
        for batch in result:
            at=0
            while at<len(batch):
                at+=struct.unpack_from('<i',batch,at)[0];count+=1
        return dict(result_rows=count)

    def close(self):
        self.client.close()


class Asterix:
    def __init__(self,system,config,namespace,threads,cpus):
        self.system=system
        self.config,self.namespace,self.threads=config,identifier(namespace),threads
        self.meta=activate(system,config,cpus)
        self.session=requests.Session()
        self.command('CREATE DATAVERSE '+self.namespace+' IF NOT EXISTS')
        cluster=self.session.get(config['url']+'/admin/cluster',timeout=30).json()
        node=self.session.get(config['url']+'/admin/cluster/node/formal_nc/config',timeout=30).json()
        self.meta.update(version=self.session.get(config['url']+'/admin/version',timeout=30).json(),
            storage_format='explicit row LSM',dataset_formats={},storage_partitions=4,
            result_manager_memory=0,
            compiler_parallelism=threads,jvm_arguments=node.get('input_arguments'),
            node_processors=node.get('num_processors'),
            settings={k:v for k,v in cluster.get('config',{}).items()
                      if k.startswith(('storage.','compiler.'))})
        # Verify the effective setting exposed by the running NC, not just the
        # configuration file written before startup.
        def find(value,key):
            if isinstance(value,list):
                for item in value:
                    result=find(item,key)
                    if result is not None:return result
            if isinstance(value,dict):
                if key in value:return value[key]
                for item in value.values():
                    result=find(item,key)
                    if result is not None:return result
            return None
        actual=find(node,'storage.buffercache.size')
        if actual is None or int(actual)!=config['cache_gib']*1024**3:
            raise RuntimeError('AsterixDB effective buffer cache could not be verified')

    def request(self,statement,stream=False,parameters=None):
        statement=f'SET `compiler.parallelism` "{self.threads}"; '+statement.strip().rstrip(';')+';'
        response=self.session.post(self.config['url']+'/query/service',
            data={'statement':statement,'pretty':'false',**(parameters or {})},timeout=3600,stream=stream)
        if not response.ok:
            raise RuntimeError('AsterixDB HTTP error: '+response.text[:3000])
        return response

    @staticmethod
    def decode(payload):
        result=json.loads(payload)
        if result.get('status')!='success':
            raise RuntimeError('AsterixDB: '+str(result.get('errors',result)))
        if result.get('warnings'):
            raise RuntimeError('AsterixDB warnings: '+str(result['warnings']))
        return result

    def command(self,statement):
        return self.decode(self.request(statement).content)

    def exists(self,table):
        namespace,dataset=map(identifier,table.split('.'))
        rows=self.command(f'SELECT VALUE d.DatasetFormat FROM Metadata.`Dataset` d WHERE d.DataverseName="{namespace}" AND d.DatasetName="{dataset}"')['results']
        if rows:
            if rows != [{'Format':'ROW'}]:
                raise RuntimeError(f'AsterixDB dataset {table} is not verified ROW: {rows}')
            self.meta['dataset_formats'][table]=rows[0]
        return bool(rows)

    def register(self,schema):
        return None

    def ingest(self,table,files,schema_id,replace_nul=False,normalize_duplicate_keys=False):
        if normalize_duplicate_keys:
            import orjson
        def documents():
            for ident,text in source_rows(files,replace_nul):
                if normalize_duplicate_keys:
                    text=orjson.dumps(orjson.loads(text))
                yield (b'{"doc_id":'+str(ident).encode()+b',"doc":'+text+b'}\n')
        self.load_json(table,documents())

    def load_json(self,table,documents):
        # Native socket-client bulk loader: no pre-scan, staged JSONL files or
        # disk write/read round trip in the import path. EOF ends the load.
        with socket.socket() as server:
            server.bind(('127.0.0.1',0));server.listen(1);server.settimeout(.25)
            port=server.getsockname()[1]
            statement=f'LOAD DATASET {table} USING `socket-client` (("sockets"="127.0.0.1:{port}"),("format"="json"));'
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(self.command,statement)
                try:
                    deadline=time.monotonic()+60
                    while True:
                        try:
                            connection,_=server.accept();break
                        except socket.timeout:
                            if future.done():future.result()
                            if time.monotonic()>=deadline:raise
                    with connection:
                        connection.settimeout(300)
                        pending=bytearray()
                        for document in documents:
                            pending.extend(document)
                            if len(pending)>=1024**2:
                                connection.sendall(pending);pending.clear()
                        if pending:connection.sendall(pending)
                except socket.timeout:
                    if future.done():future.result()
                    raise
                future.result()

    def validate(self,table,expected):
        result=self.command(f'SELECT count(*) AS n,min(d.doc_id) AS lo,max(d.doc_id) AS hi '
            f'FROM {table} d')['results']
        if result!=[dict(n=expected,lo=0,hi=expected-1)]:
            raise RuntimeError('AsterixDB row/doc_id validation failed: '+str(result))

    def maintain(self,table):
        # LOAD is synchronous and creates disk components before returning.
        pass

    def dataset_paths(self,table):
        namespace,dataset=map(identifier,table.split('.'))
        root=Path(self.config['directory'])/'data'
        return [p for part in root.glob('p*') for p in part.rglob('*')
                if p.is_file() and namespace in p.parts and any(x.startswith(dataset+'_') or x==dataset for x in p.parts)]

    def storage(self,table):
        paths=self.dataset_paths(table)
        if not paths:
            raise RuntimeError('AsterixDB dataset files not located; cannot report size')
        return dict(disk_bytes=sum(p.stat().st_size for p in paths),
            scope='AsterixDB dataset primary/index component files; excludes shared metadata/transaction logs',
            file_count=len(paths))

    def drop(self,table):
        paths=self.dataset_paths(table)
        self.command('DROP DATASET '+table+' IF EXISTS; DROP TYPE '+table+'_type IF EXISTS')
        if any(p.exists() for p in paths):
            raise RuntimeError('AsterixDB dataset files remain after drop')
        return dict(cleaned=True,method='DROP DATASET/TYPE; component file removal verified')

    def prepare(self,statement,streaming=False):
        return statement,streaming

    def receive(self,prepared):
        statement,streaming=prepared
        if not streaming:
            return self.request(statement).content
        tail=b''
        with self.request(statement,stream=True) as response:
            for chunk in response.iter_content(1024**2):
                tail=(tail+chunk)[-65536:]
        return {'tail':tail}

    def finish(self,result):
        if isinstance(result,dict):
            tail=result['tail']
            # The API's status/metrics trailer follows all result documents.
            # Decode only that trailer after timing, never the restored JSON.
            matches=list(re.finditer(rb'"status"\s*:\s*"([^"\\]*)"',tail))
            if not matches:
                raise RuntimeError('AsterixDB restore missing completion trailer')
            trailer=b'{'+tail[matches[-1].start():]
            data=self.decode(trailer)
            return dict(result_rows=data['metrics']['resultCount'])
        data=self.decode(result)
        info=dict(result_rows=len(data.get('results',[])))
        if getattr(self,'verify_results',False):
            info['result_signature']=result_signature(data.get('results',[]))
        return info

    def close(self):
        self.session.close()
