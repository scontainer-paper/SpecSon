-- query: O-C1-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.publication_year": {
              "$gte": 2020
            }
          },
          {
            "doc.cited_by_count": {
              "$gte": 50
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

-- query: O-C1-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.type": "article"
          },
          {
            "doc.publication_year": {
              "$gte": 2020
            }
          },
          {
            "doc.is_retracted": false
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

-- query: O-C1-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.authors_count": {
              "$gte": 10
            }
          },
          {
            "doc.countries_distinct_count": {
              "$gte": 3
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

-- query: O-C1-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.open_access.oa_status": "gold"
          },
          {
            "doc.cited_by_count": {
              "$gte": 20
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

-- query: O-C2-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.indexed_in": "pubmed"
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

-- query: O-C2-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.counts_by_year": {
          "$elemMatch": {
            "cited_by_count": {
              "$gte": 20
            }
          }
        }
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

-- query: O-C2-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.counts_by_year.0": {
              "$exists": true
            }
          },
          {
            "$expr": {
              "$let": {
                "vars": {
                  "operand0": {
                    "$let": {
                      "vars": {
                        "values": {
                          "$filter": {
                            "input": {
                              "$map": {
                                "input": {
                                  "$ifNull": [
                                    "$doc.counts_by_year",
                                    []
                                  ]
                                },
                                "as": "a",
                                "in": "$$a.cited_by_count"
                              }
                            },
                            "as": "value",
                            "cond": {
                              "$isNumber": "$$value"
                            }
                          }
                        }
                      },
                      "in": {
                        "$cond": [
                          {
                            "$gt": [
                              {
                                "$size": "$$values"
                              },
                              0
                            ]
                          },
                          {
                            "$sum": "$$values"
                          },
                          null
                        ]
                      }
                    }
                  }
                },
                "in": {
                  "$and": [
                    {
                      "$ne": [
                        {
                          "$ifNull": [
                            "$$operand0",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$gte": [
                        "$$operand0",
                        100
                      ]
                    }
                  ]
                }
              }
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

-- query: O-C2-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.counts_by_year.0": {
              "$exists": true
            }
          },
          {
            "$expr": {
              "$let": {
                "vars": {
                  "operand0": {
                    "$avg": {
                      "$map": {
                        "input": {
                          "$ifNull": [
                            "$doc.counts_by_year",
                            []
                          ]
                        },
                        "as": "a",
                        "in": "$$a.cited_by_count"
                      }
                    }
                  }
                },
                "in": {
                  "$and": [
                    {
                      "$ne": [
                        {
                          "$ifNull": [
                            "$$operand0",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$gte": [
                        "$$operand0",
                        10
                      ]
                    }
                  ]
                }
              }
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

-- query: O-C3-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.locations": {
          "$elemMatch": {
            "$and": [
              {
                "is_oa": true
              },
              {
                "is_published": true
              },
              {
                "source.type": "journal"
              }
            ]
          }
        }
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

-- query: O-C3-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.authorships": {
          "$elemMatch": {
            "$and": [
              {
                "is_corresponding": true
              },
              {
                "institutions": {
                  "$elemMatch": {
                    "$and": [
                      {
                        "country_code": "US"
                      },
                      {
                        "type": "education"
                      }
                    ]
                  }
                }
              }
            ]
          }
        }
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

-- query: O-C3-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.authorships": {
          "$elemMatch": {
            "$and": [
              {
                "author_position": "first"
              },
              {
                "institutions": {
                  "$elemMatch": {
                    "$and": [
                      {
                        "country_code": "GB"
                      },
                      {
                        "type": "healthcare"
                      }
                    ]
                  }
                }
              }
            ]
          }
        }
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

-- query: O-C3-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.counts_by_year": {
          "$elemMatch": {
            "$and": [
              {
                "$and": [
                  {
                    "year": {
                      "$gte": 2020
                    }
                  },
                  {
                    "year": {
                      "$lte": 2024
                    }
                  }
                ]
              },
              {
                "cited_by_count": {
                  "$gte": 20
                }
              }
            ]
          }
        }
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

-- query: O-C4-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.counts_by_year": {
          "$elemMatch": {
            "$and": [
              {
                "year": {
                  "$gte": 2020
                }
              },
              {
                "year": {
                  "$lte": 2024
                }
              }
            ]
          }
        }
      }
    },
    {
      "$set": {
        "__items": {
          "$filter": {
            "input": {
              "$ifNull": [
                "$doc.counts_by_year",
                []
              ]
            },
            "as": "a",
            "cond": {
              "$and": [
                {
                  "$and": [
                    {
                      "$ne": [
                        {
                          "$ifNull": [
                            "$$a.year",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$gte": [
                        "$$a.year",
                        2020
                      ]
                    }
                  ]
                },
                {
                  "$and": [
                    {
                      "$ne": [
                        {
                          "$ifNull": [
                            "$$a.year",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$lte": [
                        "$$a.year",
                        2024
                      ]
                    }
                  ]
                }
              ]
            }
          }
        }
      }
    },
    {
      "$set": {
        "__s": {
          "total": {
            "$let": {
              "vars": {
                "values": {
                  "$filter": {
                    "input": {
                      "$map": {
                        "input": "$__items",
                        "as": "a",
                        "in": "$$a.cited_by_count"
                      }
                    },
                    "as": "value",
                    "cond": {
                      "$isNumber": "$$value"
                    }
                  }
                }
              },
              "in": {
                "$cond": [
                  {
                    "$gt": [
                      {
                        "$size": "$$values"
                      },
                      0
                    ]
                  },
                  {
                    "$sum": "$$values"
                  },
                  null
                ]
              }
            }
          },
          "average": {
            "$avg": {
              "$map": {
                "input": "$__items",
                "as": "a",
                "in": "$$a.cited_by_count"
              }
            }
          },
          "years": {
            "$size": "$__items"
          }
        }
      }
    },
    {
      "$match": {
        "$expr": {
          "$and": [
            {
              "$ne": [
                {
                  "$ifNull": [
                    "$__s.total",
                    null
                  ]
                },
                null
              ]
            },
            {
              "$gte": [
                "$__s.total",
                50
              ]
            }
          ]
        }
      }
    },
    {
      "$project": {
        "_id": 0,
        "doc_id": 1,
        "result": {
          "id": {
            "$ifNull": [
              "$doc.id",
              null
            ]
          },
          "title": {
            "$ifNull": [
              "$doc.title",
              null
            ]
          },
          "publication_year": {
            "$ifNull": [
              "$doc.publication_year",
              null
            ]
          },
          "citations_2020_2024": {
            "$ifNull": [
              "$__s.total",
              null
            ]
          },
          "avg_recorded_year": {
            "$ifNull": [
              "$__s.average",
              null
            ]
          },
          "recorded_years": {
            "$ifNull": [
              "$__s.years",
              null
            ]
          }
        }
      }
    }
  ]
}

-- query: O-C4-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.authorships": {
          "$elemMatch": {
            "$and": [
              {
                "is_corresponding": true
              },
              {
                "institutions": {
                  "$elemMatch": {
                    "$and": [
                      {
                        "country_code": "US"
                      },
                      {
                        "type": "education"
                      }
                    ]
                  }
                }
              }
            ]
          }
        }
      }
    },
    {
      "$match": {
        "doc.counts_by_year": {
          "$elemMatch": {
            "$and": [
              {
                "year": {
                  "$gte": 2020
                }
              },
              {
                "year": {
                  "$lte": 2024
                }
              }
            ]
          }
        }
      }
    },
    {
      "$set": {
        "__items": {
          "$filter": {
            "input": {
              "$ifNull": [
                "$doc.counts_by_year",
                []
              ]
            },
            "as": "a",
            "cond": {
              "$and": [
                {
                  "$and": [
                    {
                      "$ne": [
                        {
                          "$ifNull": [
                            "$$a.year",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$gte": [
                        "$$a.year",
                        2020
                      ]
                    }
                  ]
                },
                {
                  "$and": [
                    {
                      "$ne": [
                        {
                          "$ifNull": [
                            "$$a.year",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$lte": [
                        "$$a.year",
                        2024
                      ]
                    }
                  ]
                }
              ]
            }
          }
        }
      }
    },
    {
      "$set": {
        "__s": {
          "total": {
            "$let": {
              "vars": {
                "values": {
                  "$filter": {
                    "input": {
                      "$map": {
                        "input": "$__items",
                        "as": "a",
                        "in": "$$a.cited_by_count"
                      }
                    },
                    "as": "value",
                    "cond": {
                      "$isNumber": "$$value"
                    }
                  }
                }
              },
              "in": {
                "$cond": [
                  {
                    "$gt": [
                      {
                        "$size": "$$values"
                      },
                      0
                    ]
                  },
                  {
                    "$sum": "$$values"
                  },
                  null
                ]
              }
            }
          },
          "average": {
            "$avg": {
              "$map": {
                "input": "$__items",
                "as": "a",
                "in": "$$a.cited_by_count"
              }
            }
          }
        }
      }
    },
    {
      "$match": {
        "$expr": {
          "$and": [
            {
              "$ne": [
                {
                  "$ifNull": [
                    "$__s.total",
                    null
                  ]
                },
                null
              ]
            },
            {
              "$gte": [
                "$__s.total",
                1
              ]
            }
          ]
        }
      }
    },
    {
      "$project": {
        "_id": 0,
        "doc_id": 1,
        "result": {
          "id": {
            "$ifNull": [
              "$doc.id",
              null
            ]
          },
          "title": {
            "$ifNull": [
              "$doc.title",
              null
            ]
          },
          "citations_2020_2024": {
            "$ifNull": [
              "$__s.total",
              null
            ]
          },
          "avg_recorded_year": {
            "$ifNull": [
              "$__s.average",
              null
            ]
          }
        }
      }
    }
  ]
}

-- query: O-C4-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.authorships": {
          "$elemMatch": {
            "$and": [
              {
                "is_corresponding": true
              },
              {
                "institutions": {
                  "$elemMatch": {
                    "$and": [
                      {
                        "country_code": "US"
                      },
                      {
                        "type": "education"
                      }
                    ]
                  }
                }
              }
            ]
          }
        }
      }
    },
    {
      "$set": {
        "__outer": {
          "$filter": {
            "input": {
              "$ifNull": [
                "$doc.authorships",
                []
              ]
            },
            "as": "a",
            "cond": {
              "$eq": [
                "$$a.is_corresponding",
                true
              ]
            }
          }
        }
      }
    },
    {
      "$unwind": "$__outer"
    },
    {
      "$set": {
        "__items": {
          "$filter": {
            "input": {
              "$ifNull": [
                "$__outer.institutions",
                []
              ]
            },
            "as": "i",
            "cond": {
              "$and": [
                {
                  "$eq": [
                    "$$i.country_code",
                    "US"
                  ]
                },
                {
                  "$eq": [
                    "$$i.type",
                    "education"
                  ]
                }
              ]
            }
          }
        }
      }
    },
    {
      "$set": {
        "__s": {
          "n": {
            "$size": "$__items"
          }
        }
      }
    },
    {
      "$match": {
        "$expr": {
          "$and": [
            {
              "$ne": [
                {
                  "$ifNull": [
                    "$__s.n",
                    null
                  ]
                },
                null
              ]
            },
            {
              "$gte": [
                "$__s.n",
                2
              ]
            }
          ]
        }
      }
    },
    {
      "$project": {
        "_id": 0,
        "doc_id": 1,
        "result": {
          "work_id": {
            "$ifNull": [
              "$doc.id",
              null
            ]
          },
          "title": {
            "$ifNull": [
              "$doc.title",
              null
            ]
          },
          "author_id": {
            "$ifNull": [
              "$__outer.author.id",
              null
            ]
          },
          "author_name": {
            "$ifNull": [
              "$__outer.author.display_name",
              null
            ]
          },
          "us_education_affiliations": {
            "$ifNull": [
              "$__s.n",
              null
            ]
          }
        }
      }
    }
  ]
}

-- query: O-C4-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.locations": {
          "$elemMatch": {
            "$and": [
              {
                "is_oa": true
              },
              {
                "is_published": true
              },
              {
                "license": "cc-by"
              },
              {
                "source.type": "journal"
              }
            ]
          }
        }
      }
    },
    {
      "$set": {
        "__items": {
          "$filter": {
            "input": {
              "$ifNull": [
                "$doc.locations",
                []
              ]
            },
            "as": "a",
            "cond": {
              "$and": [
                {
                  "$eq": [
                    "$$a.is_oa",
                    true
                  ]
                },
                {
                  "$eq": [
                    "$$a.is_published",
                    true
                  ]
                },
                {
                  "$eq": [
                    "$$a.license",
                    "cc-by"
                  ]
                },
                {
                  "$eq": [
                    "$$a.source.type",
                    "journal"
                  ]
                }
              ]
            }
          }
        }
      }
    },
    {
      "$set": {
        "__s": {
          "n": {
            "$size": "$__items"
          }
        }
      }
    },
    {
      "$match": {
        "$expr": {
          "$and": [
            {
              "$ne": [
                {
                  "$ifNull": [
                    "$__s.n",
                    null
                  ]
                },
                null
              ]
            },
            {
              "$gte": [
                "$__s.n",
                1
              ]
            }
          ]
        }
      }
    },
    {
      "$project": {
        "_id": 0,
        "doc_id": 1,
        "result": {
          "id": {
            "$ifNull": [
              "$doc.id",
              null
            ]
          },
          "title": {
            "$ifNull": [
              "$doc.title",
              null
            ]
          },
          "cited_by_count": {
            "$ifNull": [
              "$doc.cited_by_count",
              null
            ]
          },
          "reusable_published_locations": {
            "$ifNull": [
              "$__s.n",
              null
            ]
          }
        }
      }
    }
  ]
}
