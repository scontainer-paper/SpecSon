CREATE TYPE specson;

CREATE FUNCTION specson_in(cstring)
RETURNS specson
AS 'MODULE_PATHNAME', 'specson_in_wrapper'
LANGUAGE C IMMUTABLE STRICT PARALLEL SAFE;

CREATE FUNCTION specson_out(specson)
RETURNS cstring
AS 'MODULE_PATHNAME', 'specson_out_wrapper'
LANGUAGE C IMMUTABLE STRICT PARALLEL SAFE;

CREATE FUNCTION specson_send(specson)
RETURNS bytea
AS 'MODULE_PATHNAME', 'specson_send_wrapper'
LANGUAGE C IMMUTABLE STRICT PARALLEL SAFE;

CREATE TYPE specson (
    INPUT = specson_in,
    OUTPUT = specson_out,
    SEND = specson_send,
    INTERNALLENGTH = variable,
    STORAGE = external
);

CREATE TYPE specson_plan;

CREATE FUNCTION specson_plan_in(cstring)
RETURNS specson_plan
AS 'MODULE_PATHNAME', 'specson_plan_in_wrapper'
LANGUAGE C IMMUTABLE STRICT PARALLEL SAFE;

CREATE FUNCTION specson_plan_out(specson_plan)
RETURNS cstring
AS 'MODULE_PATHNAME', 'specson_plan_out_wrapper'
LANGUAGE C IMMUTABLE STRICT PARALLEL SAFE;

CREATE TYPE specson_plan (
    INPUT = specson_plan_in,
    OUTPUT = specson_plan_out,
    INTERNALLENGTH = variable,
    STORAGE = plain
);

CREATE FUNCTION specson_register_schema(bigint, text)
RETURNS bigint
AS 'MODULE_PATHNAME', 'specson_register_schema_wrapper'
LANGUAGE C VOLATILE STRICT PARALLEL UNSAFE;

CREATE FUNCTION specson_encode_begin(bigint)
RETURNS bigint
AS 'MODULE_PATHNAME', 'specson_encode_begin_wrapper'
LANGUAGE C VOLATILE STRICT PARALLEL UNSAFE;

CREATE FUNCTION specson_encode(text)
RETURNS specson
AS 'MODULE_PATHNAME', 'specson_encode_wrapper'
LANGUAGE C VOLATILE STRICT PARALLEL UNSAFE;

CREATE FUNCTION specson_encode_end()
RETURNS bigint
AS 'MODULE_PATHNAME', 'specson_encode_end_wrapper'
LANGUAGE C VOLATILE STRICT PARALLEL UNSAFE;

CREATE FUNCTION specson_restore(specson)
RETURNS text
AS 'MODULE_PATHNAME', 'specson_restore_wrapper'
LANGUAGE C VOLATILE STRICT PARALLEL UNSAFE;

CREATE FUNCTION specson_query_count_installed(specson_plan, specson)
RETURNS bigint
AS 'MODULE_PATHNAME', 'specson_query_count_installed_wrapper'
LANGUAGE C VOLATILE STRICT PARALLEL UNSAFE;

CREATE FUNCTION specson_query_exists_installed(specson_plan, specson)
RETURNS boolean
AS 'MODULE_PATHNAME', 'specson_query_exists_installed_wrapper'
LANGUAGE C VOLATILE STRICT PARALLEL UNSAFE;

CREATE FUNCTION specson_query_support(internal)
RETURNS internal
AS 'MODULE_PATHNAME', 'specson_query_support_wrapper'
LANGUAGE C IMMUTABLE STRICT PARALLEL UNSAFE;

CREATE FUNCTION specson_query_count(bigint, specson, text)
RETURNS bigint
AS 'MODULE_PATHNAME', 'specson_query_count_unplanned_wrapper'
LANGUAGE C VOLATILE STRICT PARALLEL UNSAFE
SUPPORT specson_query_support;

CREATE FUNCTION specson_query_exists(bigint, specson, text)
RETURNS boolean
AS 'MODULE_PATHNAME', 'specson_query_exists_unplanned_wrapper'
LANGUAGE C VOLATILE STRICT PARALLEL UNSAFE
SUPPORT specson_query_support;
