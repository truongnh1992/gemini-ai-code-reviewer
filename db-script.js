db.runCommand( {
    createSearchIndexes: "Conversation",
    indexes: [
       {
          name: "default_sre",
          definition: {
            "mappings": {
            "dynamic": false,
            "fields": {
                "ContactDisplayId": {
                    "analyzer": "containing_analyzer",
                    "searchAnalyzer": "lowercase_keyword_analyzer",
                    "type": "string"
                },
                "ContactName": {
                    "analyzer": "containing_analyzer",
                    "searchAnalyzer": "lowercase_keyword_analyzer",
                    "type": "string"
                },
                "ContactWaId": {
                    "analyzer": "containing_analyzer",
                    "searchAnalyzer": "lucene.keyword";
                    "type": "string",
                },
                "LastUpdated": {
                    "type": "date"
                },
                "TenantId": {
                    "type": "token"
                },
                "TicketFilteringInfo": {
                    "fields": {
                        "TicketStatus": {
                            "type": "number"
                        }
                    },
                    "type": "document"
                },
                "_t": {
                    "type": "token"
                }
            }
        },
        "analyzers": [
            {
                "name": "lowercase_keyword_analyzer",
                "tokenFilters": [
                    {
                        "type": "lowercase"
                    }
                ],
                "tokenizer": {
                    "type": "keyword"
                }
            },
            {
                "name": "containing_analyzer",
                "tokenFilters": [
                    {
                        "type": "lowercase"
                    }
                ],
                "tokenizer": {
                    "maxGram": 50,
                    "minGram": 3,
                    "type": "nGram"
                }
            }
        ]
        },
       }
    ]
} )
