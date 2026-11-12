-- query: H-C1-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.orderstatus": "O"
          },
          {
            "doc.totalprice": {
              "$gte": 200000
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

-- query: H-C1-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.customer.mktsegment": "AUTOMOBILE"
          },
          {
            "doc.customer.acctbal": {
              "$lt": 0
            }
          },
          {
            "doc.totalprice": {
              "$gte": 100000
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

-- query: H-C1-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.orderdate": {
              "$gte": "1995-01-01"
            }
          },
          {
            "doc.orderdate": {
              "$lt": "1996-01-01"
            }
          },
          {
            "doc.totalprice": {
              "$gte": 150000
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

-- query: H-C1-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.customer.nation.region.name": "EUROPE"
          },
          {
            "doc.orderpriority": "1-URGENT"
          },
          {
            "doc.totalprice": {
              "$gte": 100000
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

-- query: H-C2-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.lineitems.0": {
              "$exists": true
            }
          },
          {
            "$expr": {
              "$gt": [
                {
                  "$size": {
                    "$filter": {
                      "input": {
                        "$ifNull": [
                          "$doc.lineitems",
                          []
                        ]
                      },
                      "as": "a",
                      "cond": {
                        "$and": [
                          {
                            "$ne": [
                              {
                                "$ifNull": [
                                  "$$a.receiptdate",
                                  null
                                ]
                              },
                              null
                            ]
                          },
                          {
                            "$ne": [
                              {
                                "$ifNull": [
                                  "$$a.commitdate",
                                  null
                                ]
                              },
                              null
                            ]
                          },
                          {
                            "$gt": [
                              "$$a.receiptdate",
                              "$$a.commitdate"
                            ]
                          }
                        ]
                      },
                      "limit": 1
                    }
                  }
                },
                0
              ]
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

-- query: H-C2-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.lineitems": {
          "$elemMatch": {
            "returnflag": "R"
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

-- query: H-C2-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.lineitems.0": {
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
                                    "$doc.lineitems",
                                    []
                                  ]
                                },
                                "as": "a",
                                "in": "$$a.quantity"
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
                        200
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

-- query: H-C2-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.lineitems.0": {
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
                            "$doc.lineitems",
                            []
                          ]
                        },
                        "as": "a",
                        "in": "$$a.quantity"
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
                        30
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

-- query: H-C3-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.lineitems": {
          "$elemMatch": {
            "$and": [
              {
                "shipmode": "AIR"
              },
              {
                "quantity": {
                  "$gte": 30
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

-- query: H-C3-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.lineitems": {
              "$elemMatch": {
                "partsupp.supplier.nation.name": "SAUDI ARABIA"
              }
            }
          },
          {
            "$expr": {
              "$gt": [
                {
                  "$size": {
                    "$filter": {
                      "input": {
                        "$ifNull": [
                          "$doc.lineitems",
                          []
                        ]
                      },
                      "as": "a",
                      "cond": {
                        "$and": [
                          {
                            "$eq": [
                              "$$a.partsupp.supplier.nation.name",
                              "SAUDI ARABIA"
                            ]
                          },
                          {
                            "$and": [
                              {
                                "$ne": [
                                  {
                                    "$ifNull": [
                                      "$$a.receiptdate",
                                      null
                                    ]
                                  },
                                  null
                                ]
                              },
                              {
                                "$ne": [
                                  {
                                    "$ifNull": [
                                      "$$a.commitdate",
                                      null
                                    ]
                                  },
                                  null
                                ]
                              },
                              {
                                "$gt": [
                                  "$$a.receiptdate",
                                  "$$a.commitdate"
                                ]
                              }
                            ]
                          }
                        ]
                      },
                      "limit": 1
                    }
                  }
                },
                0
              ]
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

-- query: H-C3-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.lineitems": {
          "$elemMatch": {
            "$and": [
              {
                "partsupp.part.brand": "Brand#12"
              },
              {
                "partsupp.part.size": {
                  "$gte": 20
                }
              },
              {
                "quantity": {
                  "$lte": 10
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

-- query: H-C3-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.lineitems": {
              "$elemMatch": {
                "shipmode": "SHIP"
              }
            }
          },
          {
            "$expr": {
              "$gt": [
                {
                  "$size": {
                    "$filter": {
                      "input": {
                        "$ifNull": [
                          "$doc.lineitems",
                          []
                        ]
                      },
                      "as": "a",
                      "cond": {
                        "$and": [
                          {
                            "$eq": [
                              "$$a.shipmode",
                              "SHIP"
                            ]
                          },
                          {
                            "$and": [
                              {
                                "$and": [
                                  {
                                    "$ne": [
                                      {
                                        "$ifNull": [
                                          "$$a.partsupp.supplier.nation.name",
                                          null
                                        ]
                                      },
                                      null
                                    ]
                                  },
                                  {
                                    "$ne": [
                                      "$$a.partsupp.supplier.nation.name",
                                      null
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
                                          "$doc.customer.nation.name",
                                          null
                                        ]
                                      },
                                      null
                                    ]
                                  },
                                  {
                                    "$ne": [
                                      "$doc.customer.nation.name",
                                      null
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
                                          "$$a.partsupp.supplier.nation.name",
                                          null
                                        ]
                                      },
                                      null
                                    ]
                                  },
                                  {
                                    "$ne": [
                                      {
                                        "$ifNull": [
                                          "$doc.customer.nation.name",
                                          null
                                        ]
                                      },
                                      null
                                    ]
                                  },
                                  {
                                    "$ne": [
                                      "$$a.partsupp.supplier.nation.name",
                                      "$doc.customer.nation.name"
                                    ]
                                  }
                                ]
                              }
                            ]
                          }
                        ]
                      },
                      "limit": 1
                    }
                  }
                },
                0
              ]
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

-- query: H-C4-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.lineitems": {
          "$elemMatch": {
            "linestatus": "F"
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
                "$doc.lineitems",
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
                            "$$a.receiptdate",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$ne": [
                        {
                          "$ifNull": [
                            "$$a.commitdate",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$gt": [
                        "$$a.receiptdate",
                        "$$a.commitdate"
                      ]
                    }
                  ]
                },
                {
                  "$eq": [
                    "$$a.linestatus",
                    "F"
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
        "__key": {
          "$setUnion": [
            {
              "$map": {
                "input": "$__items",
                "as": "a",
                "in": {
                  "$ifNull": [
                    "$$a.shipmode",
                    null
                  ]
                }
              }
            },
            []
          ]
        }
      }
    },
    {
      "$unwind": "$__key"
    },
    {
      "$set": {
        "__items": {
          "$filter": {
            "input": "$__items",
            "as": "a",
            "cond": {
              "$eq": [
                {
                  "$ifNull": [
                    "$$a.shipmode",
                    null
                  ]
                },
                "$__key"
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
          },
          "gross": {
            "$let": {
              "vars": {
                "values": {
                  "$filter": {
                    "input": {
                      "$map": {
                        "input": "$__items",
                        "as": "a",
                        "in": "$$a.extendedprice"
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
                "in": "$$a.quantity"
              }
            }
          },
          "key": "$__key"
        }
      }
    },
    {
      "$match": {
        "$expr": true
      }
    },
    {
      "$project": {
        "_id": 0,
        "doc_id": 1,
        "result": {
          "orderkey": {
            "$ifNull": [
              "$doc.orderkey",
              null
            ]
          },
          "priority": {
            "$ifNull": [
              "$doc.orderpriority",
              null
            ]
          },
          "customer_country": {
            "$ifNull": [
              "$doc.customer.nation.name",
              null
            ]
          },
          "shipmode": {
            "$ifNull": [
              "$__s.key",
              null
            ]
          },
          "late_lines": {
            "$ifNull": [
              "$__s.n",
              null
            ]
          },
          "gross_value": {
            "$ifNull": [
              "$__s.gross",
              null
            ]
          },
          "avg_quantity": {
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

-- query: H-C4-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.orderstatus": "F"
      }
    },
    {
      "$match": {
        "doc.lineitems": {
          "$elemMatch": {
            "$and": [
              {
                "returnflag": "R"
              },
              {
                "linestatus": "F"
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
                "$doc.lineitems",
                []
              ]
            },
            "as": "a",
            "cond": {
              "$and": [
                {
                  "$eq": [
                    "$$a.returnflag",
                    "R"
                  ]
                },
                {
                  "$eq": [
                    "$$a.linestatus",
                    "F"
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
        "__key": {
          "$setUnion": [
            {
              "$map": {
                "input": "$__items",
                "as": "a",
                "in": {
                  "$ifNull": [
                    "$$a.partsupp.supplier.nation.name",
                    null
                  ]
                }
              }
            },
            []
          ]
        }
      }
    },
    {
      "$unwind": "$__key"
    },
    {
      "$set": {
        "__items": {
          "$filter": {
            "input": "$__items",
            "as": "a",
            "cond": {
              "$eq": [
                {
                  "$ifNull": [
                    "$$a.partsupp.supplier.nation.name",
                    null
                  ]
                },
                "$__key"
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
          },
          "gross": {
            "$let": {
              "vars": {
                "values": {
                  "$filter": {
                    "input": {
                      "$map": {
                        "input": "$__items",
                        "as": "a",
                        "in": "$$a.extendedprice"
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
                "in": "$$a.discount"
              }
            }
          },
          "key": "$__key"
        }
      }
    },
    {
      "$match": {
        "$expr": true
      }
    },
    {
      "$project": {
        "_id": 0,
        "doc_id": 1,
        "result": {
          "orderkey": {
            "$ifNull": [
              "$doc.orderkey",
              null
            ]
          },
          "customer": {
            "$ifNull": [
              "$doc.customer.name",
              null
            ]
          },
          "supplier_country": {
            "$ifNull": [
              "$__s.key",
              null
            ]
          },
          "returned_lines": {
            "$ifNull": [
              "$__s.n",
              null
            ]
          },
          "gross_value": {
            "$ifNull": [
              "$__s.gross",
              null
            ]
          },
          "avg_discount": {
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

-- query: H-C4-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.lineitems": {
          "$elemMatch": {
            "shipmode": "AIR"
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
                "$doc.lineitems",
                []
              ]
            },
            "as": "a",
            "cond": {
              "$and": [
                {
                  "$eq": [
                    "$$a.shipmode",
                    "AIR"
                  ]
                },
                {
                  "$and": [
                    {
                      "$and": [
                        {
                          "$ne": [
                            {
                              "$ifNull": [
                                "$$a.partsupp.supplier.nation.name",
                                null
                              ]
                            },
                            null
                          ]
                        },
                        {
                          "$ne": [
                            "$$a.partsupp.supplier.nation.name",
                            null
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
                                "$doc.customer.nation.name",
                                null
                              ]
                            },
                            null
                          ]
                        },
                        {
                          "$ne": [
                            "$doc.customer.nation.name",
                            null
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
                                "$$a.partsupp.supplier.nation.name",
                                null
                              ]
                            },
                            null
                          ]
                        },
                        {
                          "$ne": [
                            {
                              "$ifNull": [
                                "$doc.customer.nation.name",
                                null
                              ]
                            },
                            null
                          ]
                        },
                        {
                          "$ne": [
                            "$$a.partsupp.supplier.nation.name",
                            "$doc.customer.nation.name"
                          ]
                        }
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
          "n": {
            "$size": "$__items"
          },
          "gross": {
            "$let": {
              "vars": {
                "values": {
                  "$filter": {
                    "input": {
                      "$map": {
                        "input": "$__items",
                        "as": "a",
                        "in": "$$a.extendedprice"
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
          "quantity": {
            "$let": {
              "vars": {
                "values": {
                  "$filter": {
                    "input": {
                      "$map": {
                        "input": "$__items",
                        "as": "a",
                        "in": "$$a.quantity"
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
          "orderkey": {
            "$ifNull": [
              "$doc.orderkey",
              null
            ]
          },
          "orderdate": {
            "$ifNull": [
              "$doc.orderdate",
              null
            ]
          },
          "customer_country": {
            "$ifNull": [
              "$doc.customer.nation.name",
              null
            ]
          },
          "air_lines": {
            "$ifNull": [
              "$__s.n",
              null
            ]
          },
          "quantity": {
            "$ifNull": [
              "$__s.quantity",
              null
            ]
          },
          "gross_value": {
            "$ifNull": [
              "$__s.gross",
              null
            ]
          }
        }
      }
    }
  ]
}

-- query: H-C4-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$or": [
          {
            "doc.orderpriority": "1-URGENT"
          },
          {
            "doc.orderpriority": "2-HIGH"
          }
        ]
      }
    },
    {
      "$match": {
        "doc.lineitems": {
          "$elemMatch": {
            "$and": [
              {
                "partsupp.part.size": {
                  "$gte": 20
                }
              },
              {
                "quantity": {
                  "$gte": 30
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
                "$doc.lineitems",
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
                            "$$a.partsupp.part.size",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$gte": [
                        "$$a.partsupp.part.size",
                        20
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
                            "$$a.quantity",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$gte": [
                        "$$a.quantity",
                        30
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
          "n": {
            "$size": "$__items"
          },
          "gross": {
            "$let": {
              "vars": {
                "values": {
                  "$filter": {
                    "input": {
                      "$map": {
                        "input": "$__items",
                        "as": "a",
                        "in": "$$a.extendedprice"
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
                "in": "$$a.quantity"
              }
            }
          },
          "quantity": {
            "$let": {
              "vars": {
                "values": {
                  "$filter": {
                    "input": {
                      "$map": {
                        "input": "$__items",
                        "as": "a",
                        "in": "$$a.quantity"
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
          "orderkey": {
            "$ifNull": [
              "$doc.orderkey",
              null
            ]
          },
          "priority": {
            "$ifNull": [
              "$doc.orderpriority",
              null
            ]
          },
          "segment": {
            "$ifNull": [
              "$doc.customer.mktsegment",
              null
            ]
          },
          "large_lines": {
            "$ifNull": [
              "$__s.n",
              null
            ]
          },
          "quantity": {
            "$ifNull": [
              "$__s.quantity",
              null
            ]
          },
          "gross_value": {
            "$ifNull": [
              "$__s.gross",
              null
            ]
          },
          "avg_quantity": {
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
