-- query: G-C1-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.payload.issue.state": "open"
          },
          {
            "doc.payload.issue.comments": {
              "$gte": 10
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

-- query: G-C1-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.type": "ForkEvent"
          },
          {
            "doc.payload.forkee.size": {
              "$gte": 10240
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

-- query: G-C1-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.payload.issue.state": "open"
          },
          {
            "doc.payload.issue.reactions.total_count": {
              "$gte": 5
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

-- query: G-C1-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.type": "IssueCommentEvent"
          },
          {
            "doc.payload.action": "created"
          },
          {
            "doc.payload.issue.comments": {
              "$gte": 5
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

-- query: G-C2-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.payload.issue.labels": {
          "$elemMatch": {
            "name": "bug"
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

-- query: G-C2-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.payload.release.assets": {
          "$elemMatch": {
            "size": {
              "$gte": 104857600
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

-- query: G-C2-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.payload.release.assets.0": {
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
                                    "$doc.payload.release.assets",
                                    []
                                  ]
                                },
                                "as": "a",
                                "in": "$$a.size"
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
                        104857600
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

-- query: G-C2-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.payload.release.assets.0": {
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
                            "$doc.payload.release.assets",
                            []
                          ]
                        },
                        "as": "a",
                        "in": "$$a.size"
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
                        10485760
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

-- query: G-C3-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.payload.release.assets": {
          "$elemMatch": {
            "$and": [
              {
                "size": {
                  "$gte": 10485760
                }
              },
              {
                "content_type": "application/zip"
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

-- query: G-C3-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.payload.issue.assignees": {
              "$elemMatch": {
                "type": "User"
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
                          "$doc.payload.issue.assignees",
                          []
                        ]
                      },
                      "as": "a",
                      "cond": {
                        "$and": [
                          {
                            "$eq": [
                              "$$a.type",
                              "User"
                            ]
                          },
                          {
                            "$and": [
                              {
                                "$ne": [
                                  {
                                    "$ifNull": [
                                      "$$a.login",
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
                                      "$doc.payload.issue.user.login",
                                      null
                                    ]
                                  },
                                  null
                                ]
                              },
                              {
                                "$eq": [
                                  "$$a.login",
                                  "$doc.payload.issue.user.login"
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

-- query: G-C3-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.payload.pages": {
          "$elemMatch": {
            "$and": [
              {
                "page_name": "Home"
              },
              {
                "action": "edited"
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

-- query: G-C3-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.payload.release.assets": {
          "$elemMatch": {
            "$and": [
              {
                "state": "uploaded"
              },
              {
                "content_type": "application/zip"
              },
              {
                "uploader.type": "Bot"
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

-- query: G-C4-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.payload.release.assets": {
          "$elemMatch": {
            "$and": [
              {
                "state": "uploaded"
              },
              {
                "size": {
                  "$gte": 1048576
                }
              },
              {
                "content_type": "application/octet-stream"
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
                "$doc.payload.release.assets",
                []
              ]
            },
            "as": "a",
            "cond": {
              "$and": [
                {
                  "$eq": [
                    "$$a.state",
                    "uploaded"
                  ]
                },
                {
                  "$and": [
                    {
                      "$ne": [
                        {
                          "$ifNull": [
                            "$$a.size",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$gte": [
                        "$$a.size",
                        1048576
                      ]
                    }
                  ]
                },
                {
                  "$eq": [
                    "$$a.content_type",
                    "application/octet-stream"
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
          "bytes": {
            "$let": {
              "vars": {
                "values": {
                  "$filter": {
                    "input": {
                      "$map": {
                        "input": "$__items",
                        "as": "a",
                        "in": "$$a.size"
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
          "downloads": {
            "$let": {
              "vars": {
                "values": {
                  "$filter": {
                    "input": {
                      "$map": {
                        "input": "$__items",
                        "as": "a",
                        "in": "$$a.download_count"
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
          "repository": {
            "$ifNull": [
              "$doc.repo.name",
              null
            ]
          },
          "tag": {
            "$ifNull": [
              "$doc.payload.release.tag_name",
              null
            ]
          },
          "assets": {
            "$ifNull": [
              "$__s.n",
              null
            ]
          },
          "bytes": {
            "$ifNull": [
              "$__s.bytes",
              null
            ]
          },
          "downloads": {
            "$ifNull": [
              "$__s.downloads",
              null
            ]
          }
        }
      }
    }
  ]
}

-- query: G-C4-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.payload.release.assets": {
          "$elemMatch": {
            "$and": [
              {
                "state": "uploaded"
              },
              {
                "content_type": "application/zip"
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
                "$doc.payload.release.assets",
                []
              ]
            },
            "as": "a",
            "cond": {
              "$and": [
                {
                  "$eq": [
                    "$$a.state",
                    "uploaded"
                  ]
                },
                {
                  "$eq": [
                    "$$a.content_type",
                    "application/zip"
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
          "bytes": {
            "$let": {
              "vars": {
                "values": {
                  "$filter": {
                    "input": {
                      "$map": {
                        "input": "$__items",
                        "as": "a",
                        "in": "$$a.size"
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
                "in": "$$a.size"
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
                    "$__s.average",
                    null
                  ]
                },
                null
              ]
            },
            {
              "$gte": [
                "$__s.average",
                10485760
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
          "repository": {
            "$ifNull": [
              "$doc.repo.name",
              null
            ]
          },
          "tag": {
            "$ifNull": [
              "$doc.payload.release.tag_name",
              null
            ]
          },
          "zip_assets": {
            "$ifNull": [
              "$__s.n",
              null
            ]
          },
          "bytes": {
            "$ifNull": [
              "$__s.bytes",
              null
            ]
          },
          "avg_bytes": {
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

-- query: G-C4-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.payload.release.assets": {
          "$elemMatch": {
            "$and": [
              {
                "state": "uploaded"
              },
              {
                "uploader.type": "Bot"
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
                "$doc.payload.release.assets",
                []
              ]
            },
            "as": "a",
            "cond": {
              "$and": [
                {
                  "$eq": [
                    "$$a.state",
                    "uploaded"
                  ]
                },
                {
                  "$eq": [
                    "$$a.uploader.type",
                    "Bot"
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
          "downloads": {
            "$let": {
              "vars": {
                "values": {
                  "$filter": {
                    "input": {
                      "$map": {
                        "input": "$__items",
                        "as": "a",
                        "in": "$$a.download_count"
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
                "in": "$$a.size"
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
          "repository": {
            "$ifNull": [
              "$doc.repo.name",
              null
            ]
          },
          "tag": {
            "$ifNull": [
              "$doc.payload.release.tag_name",
              null
            ]
          },
          "bot_assets": {
            "$ifNull": [
              "$__s.n",
              null
            ]
          },
          "downloads": {
            "$ifNull": [
              "$__s.downloads",
              null
            ]
          },
          "avg_bytes": {
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

-- query: G-C4-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.payload.issue.state": "open"
      }
    },
    {
      "$match": {
        "doc.payload.issue.assignees": {
          "$elemMatch": {
            "type": "User"
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
                "$doc.payload.issue.assignees",
                []
              ]
            },
            "as": "a",
            "cond": {
              "$eq": [
                "$$a.type",
                "User"
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
          "hits": {
            "$sum": {
              "$map": {
                "input": "$__items",
                "as": "a",
                "in": {
                  "$cond": [
                    {
                      "$and": [
                        {
                          "$ne": [
                            {
                              "$ifNull": [
                                "$$a.login",
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
                                "$doc.payload.issue.user.login",
                                null
                              ]
                            },
                            null
                          ]
                        },
                        {
                          "$eq": [
                            "$$a.login",
                            "$doc.payload.issue.user.login"
                          ]
                        }
                      ]
                    },
                    1,
                    0
                  ]
                }
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
            },
            {
              "$and": [
                {
                  "$ne": [
                    {
                      "$ifNull": [
                        "$__s.hits",
                        null
                      ]
                    },
                    null
                  ]
                },
                {
                  "$gt": [
                    "$__s.hits",
                    0
                  ]
                }
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
          "repository": {
            "$ifNull": [
              "$doc.repo.name",
              null
            ]
          },
          "issue": {
            "$ifNull": [
              "$doc.payload.issue.html_url",
              null
            ]
          },
          "title": {
            "$ifNull": [
              "$doc.payload.issue.title",
              null
            ]
          },
          "comments": {
            "$ifNull": [
              "$doc.payload.issue.comments",
              null
            ]
          },
          "human_assignees": {
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
