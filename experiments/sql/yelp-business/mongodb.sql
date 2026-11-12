-- query: YB-C1-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.is_open": 1
          },
          {
            "doc.stars": {
              "$gte": 4
            }
          },
          {
            "doc.review_count": {
              "$gte": 100
            }
          }
        ]
      }
    },
    {
      "$project": {
        "_id": 0,
        "doc_id": 1
      }
    }
  ]
}

-- query: YB-C1-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.city": "Philadelphia"
          },
          {
            "doc.is_open": 1
          },
          {
            "doc.stars": {
              "$gte": 4
            }
          }
        ]
      }
    },
    {
      "$project": {
        "_id": 0,
        "doc_id": 1
      }
    }
  ]
}

-- query: YB-C1-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.stars": {
              "$gte": 4
            }
          },
          {
            "doc.is_open": 1
          },
          {
            "doc.attributes.GoodForKids": "True"
          },
          {
            "doc.attributes.RestaurantsTakeOut": "True"
          }
        ]
      }
    },
    {
      "$project": {
        "_id": 0,
        "doc_id": 1
      }
    }
  ]
}

-- query: YB-C1-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.review_count": {
              "$gte": 50
            }
          },
          {
            "doc.is_open": 1
          },
          {
            "doc.attributes.RestaurantsDelivery": "True"
          },
          {
            "doc.attributes.BusinessAcceptsCreditCards": "True"
          }
        ]
      }
    },
    {
      "$project": {
        "_id": 0,
        "doc_id": 1
      }
    }
  ]
}
