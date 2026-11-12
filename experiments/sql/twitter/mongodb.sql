-- query: T-C1-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.user.verified": true
          },
          {
            "doc.user.followers_count": {
              "$gte": 10000
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

-- query: T-C1-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.lang": "en"
          },
          {
            "doc.user.followers_count": {
              "$gte": 1000
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

-- query: T-C1-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.retweeted_status.lang": "en"
          },
          {
            "doc.retweeted_status.retweet_count": {
              "$gte": 1000
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

-- query: T-C1-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.is_quote_status": true
          },
          {
            "doc.quoted_status.favorite_count": {
              "$gte": 1000
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

-- query: T-C2-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.entities.hashtags": {
          "$elemMatch": {
            "text": "NowPlaying"
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

-- query: T-C2-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.extended_entities.media": {
          "$elemMatch": {
            "type": "video"
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

-- query: T-C2-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.extended_entities.media.0": {
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
                                    "$doc.extended_entities.media",
                                    []
                                  ]
                                },
                                "as": "a",
                                "in": "$$a.video_info.duration_millis"
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
                        60000
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

-- query: T-C2-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.extended_entities.media.0": {
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
                            "$doc.extended_entities.media",
                            []
                          ]
                        },
                        "as": "a",
                        "in": "$$a.video_info.duration_millis"
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
                        30000
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

-- query: T-C3-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.extended_entities.media": {
              "$elemMatch": {
                "type": "photo"
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
                          "$doc.extended_entities.media",
                          []
                        ]
                      },
                      "as": "a",
                      "cond": {
                        "$and": [
                          {
                            "$eq": [
                              "$$a.type",
                              "photo"
                            ]
                          },
                          {
                            "$and": [
                              {
                                "$ne": [
                                  {
                                    "$ifNull": [
                                      "$$a.sizes.large.w",
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
                                      "$$a.sizes.large.h",
                                      null
                                    ]
                                  },
                                  null
                                ]
                              },
                              {
                                "$gt": [
                                  "$$a.sizes.large.w",
                                  "$$a.sizes.large.h"
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

-- query: T-C3-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.extended_entities.media": {
              "$elemMatch": {
                "type": "video"
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
                          "$doc.extended_entities.media",
                          []
                        ]
                      },
                      "as": "a",
                      "cond": {
                        "$and": [
                          {
                            "$eq": [
                              "$$a.type",
                              "video"
                            ]
                          },
                          {
                            "$and": [
                              {
                                "$ne": [
                                  {
                                    "$ifNull": [
                                      "$$a.sizes.large.h",
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
                                      "$$a.sizes.large.w",
                                      null
                                    ]
                                  },
                                  null
                                ]
                              },
                              {
                                "$gt": [
                                  "$$a.sizes.large.h",
                                  "$$a.sizes.large.w"
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

-- query: T-C3-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.extended_entities.media": {
              "$elemMatch": {
                "$and": [
                  {
                    "type": "video"
                  },
                  {
                    "video_info.duration_millis": {
                      "$gte": 30000
                    }
                  }
                ]
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
                          "$doc.extended_entities.media",
                          []
                        ]
                      },
                      "as": "a",
                      "cond": {
                        "$and": [
                          {
                            "$eq": [
                              "$$a.type",
                              "video"
                            ]
                          },
                          {
                            "$and": [
                              {
                                "$ne": [
                                  {
                                    "$ifNull": [
                                      "$$a.sizes.large.w",
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
                                      "$$a.sizes.large.h",
                                      null
                                    ]
                                  },
                                  null
                                ]
                              },
                              {
                                "$gt": [
                                  "$$a.sizes.large.w",
                                  "$$a.sizes.large.h"
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
                                      "$$a.video_info.duration_millis",
                                      null
                                    ]
                                  },
                                  null
                                ]
                              },
                              {
                                "$gte": [
                                  "$$a.video_info.duration_millis",
                                  30000
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

-- query: T-C3-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.retweeted_status.retweet_count": {
              "$gte": 1000
            }
          },
          {
            "$expr": {
              "$and": [
                {
                  "$and": [
                    {
                      "$ne": [
                        {
                          "$ifNull": [
                            "$doc.retweeted_status.retweet_count",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$gte": [
                        "$doc.retweeted_status.retweet_count",
                        1000
                      ]
                    }
                  ]
                },
                {
                  "$gt": [
                    {
                      "$size": {
                        "$filter": {
                          "input": {
                            "$ifNull": [
                              "$doc.retweeted_status.extended_entities.media",
                              []
                            ]
                          },
                          "as": "a",
                          "cond": {
                            "$and": [
                              {
                                "$eq": [
                                  "$$a.type",
                                  "photo"
                                ]
                              },
                              {
                                "$and": [
                                  {
                                    "$ne": [
                                      {
                                        "$ifNull": [
                                          "$$a.sizes.large.h",
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
                                          "$$a.sizes.large.w",
                                          null
                                        ]
                                      },
                                      null
                                    ]
                                  },
                                  {
                                    "$gt": [
                                      "$$a.sizes.large.h",
                                      "$$a.sizes.large.w"
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

-- query: T-C4-1 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.extended_entities.media": {
          "$elemMatch": {
            "type": "photo"
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
                "$doc.extended_entities.media",
                []
              ]
            },
            "as": "a",
            "cond": {
              "$eq": [
                "$$a.type",
                "photo"
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
          "tweet_id": {
            "$ifNull": [
              "$doc.id_str",
              null
            ]
          },
          "author": {
            "$ifNull": [
              "$doc.user.screen_name",
              null
            ]
          },
          "followers": {
            "$ifNull": [
              "$doc.user.followers_count",
              null
            ]
          },
          "lang": {
            "$ifNull": [
              "$doc.lang",
              null
            ]
          },
          "photos": {
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

-- query: T-C4-2 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.extended_entities.media": {
          "$elemMatch": {
            "$and": [
              {
                "type": "video"
              },
              {
                "video_info.duration_millis": {
                  "$gte": 30000
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
                "$doc.extended_entities.media",
                []
              ]
            },
            "as": "a",
            "cond": {
              "$and": [
                {
                  "$eq": [
                    "$$a.type",
                    "video"
                  ]
                },
                {
                  "$and": [
                    {
                      "$ne": [
                        {
                          "$ifNull": [
                            "$$a.video_info.duration_millis",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$gte": [
                        "$$a.video_info.duration_millis",
                        30000
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
          "duration": {
            "$let": {
              "vars": {
                "values": {
                  "$filter": {
                    "input": {
                      "$map": {
                        "input": "$__items",
                        "as": "a",
                        "in": "$$a.video_info.duration_millis"
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
                "in": "$$a.video_info.duration_millis"
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
          "tweet_id": {
            "$ifNull": [
              "$doc.id_str",
              null
            ]
          },
          "author": {
            "$ifNull": [
              "$doc.user.screen_name",
              null
            ]
          },
          "followers": {
            "$ifNull": [
              "$doc.user.followers_count",
              null
            ]
          },
          "lang": {
            "$ifNull": [
              "$doc.lang",
              null
            ]
          },
          "long_videos": {
            "$ifNull": [
              "$__s.n",
              null
            ]
          },
          "duration_ms": {
            "$ifNull": [
              "$__s.duration",
              null
            ]
          },
          "avg_duration_ms": {
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

-- query: T-C4-3 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "doc.retweeted_status.retweet_count": {
          "$gte": 1000
        }
      }
    },
    {
      "$match": {
        "doc.retweeted_status.extended_entities.media": {
          "$elemMatch": {
            "$and": [
              {
                "type": "video"
              },
              {
                "video_info.duration_millis": {
                  "$gte": 30000
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
                "$doc.retweeted_status.extended_entities.media",
                []
              ]
            },
            "as": "a",
            "cond": {
              "$and": [
                {
                  "$eq": [
                    "$$a.type",
                    "video"
                  ]
                },
                {
                  "$and": [
                    {
                      "$ne": [
                        {
                          "$ifNull": [
                            "$$a.video_info.duration_millis",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$gte": [
                        "$$a.video_info.duration_millis",
                        30000
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
          "duration": {
            "$let": {
              "vars": {
                "values": {
                  "$filter": {
                    "input": {
                      "$map": {
                        "input": "$__items",
                        "as": "a",
                        "in": "$$a.video_info.duration_millis"
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
                "in": "$$a.video_info.duration_millis"
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
          "tweet_id": {
            "$ifNull": [
              "$doc.id_str",
              null
            ]
          },
          "original_id": {
            "$ifNull": [
              "$doc.retweeted_status.id_str",
              null
            ]
          },
          "original_author": {
            "$ifNull": [
              "$doc.retweeted_status.user.screen_name",
              null
            ]
          },
          "original_retweets": {
            "$ifNull": [
              "$doc.retweeted_status.retweet_count",
              null
            ]
          },
          "long_videos": {
            "$ifNull": [
              "$__s.n",
              null
            ]
          },
          "duration_ms": {
            "$ifNull": [
              "$__s.duration",
              null
            ]
          },
          "avg_duration_ms": {
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

-- query: T-C4-4 | Business query
{
  "collection": "{{table}}",
  "pipeline": [
    {
      "$match": {
        "$and": [
          {
            "doc.is_quote_status": true
          },
          {
            "doc.quoted_status.favorite_count": {
              "$gte": 1000
            }
          }
        ]
      }
    },
    {
      "$match": {
        "doc.quoted_status.extended_entities.media": {
          "$elemMatch": {
            "type": "photo"
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
                "$doc.quoted_status.extended_entities.media",
                []
              ]
            },
            "as": "a",
            "cond": {
              "$and": [
                {
                  "$eq": [
                    "$$a.type",
                    "photo"
                  ]
                },
                {
                  "$and": [
                    {
                      "$ne": [
                        {
                          "$ifNull": [
                            "$$a.sizes.large.w",
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
                            "$$a.sizes.large.h",
                            null
                          ]
                        },
                        null
                      ]
                    },
                    {
                      "$gt": [
                        "$$a.sizes.large.w",
                        "$$a.sizes.large.h"
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
          "tweet_id": {
            "$ifNull": [
              "$doc.id_str",
              null
            ]
          },
          "original_id": {
            "$ifNull": [
              "$doc.quoted_status.id_str",
              null
            ]
          },
          "original_author": {
            "$ifNull": [
              "$doc.quoted_status.user.screen_name",
              null
            ]
          },
          "original_likes": {
            "$ifNull": [
              "$doc.quoted_status.favorite_count",
              null
            ]
          },
          "landscape_photos": {
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
