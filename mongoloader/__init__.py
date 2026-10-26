from typing import Any, Protocol

from bunnet import Document

class ApplicativeMongoLoader[T](Protocol):
    def execute(self) -> T | None:
        ...

    def mongo_query(self) -> dict[str, Any]:
        ...


class FindOne[T: Document](ApplicativeMongoLoader[T]):
    def __init__(self, collection: type[T], filter: dict[str, Any]):
        self.collection = collection
        self.filter = filter

    def execute(self) -> T | None:
        return self.collection.find_one(self.filter)

    def mongo_query(self) -> dict[str, Any]:
        return self.filter


class FindTuple[T: ApplicativeMongoLoader, U: ApplicativeMongoLoader](ApplicativeMongoLoader[tuple[T | None, U | None]]):
    def __init__(self, lft: T, rgt: U):
        self.lft = lft
        self.rgt = rgt

    def execute(self) -> tuple[T | None, U | None] | None:
        lft_result = self.lft.execute()
        if lft_result is None:
            return None
        rgt_result = self.rgt.execute()
        if rgt_result is None:
            return None
        return (lft_result, rgt_result)

def ap_tuple[T, U](lft: FindOne[T], rgt: FindOne[U]) -> FindOne[tuple[T, U]]:
    return (lft.execute(), rgt.execute())



def your_turn(queries: dict[str, tuple[type[Document], Any]]) -> dict[str, Document | None]:
    all= list(queries.items())

    pipeline = [
        {"$match": all[0][1][0].find_one(all[0][1][1]).get_filter_query()},
        {"$limit": 1},
        {
            "$project": {
                "kind": {"$literal": all[0][0]},
                "doc": "$$ROOT",
            }
        },
        {
            "$unionWith": {
                "coll": all[1][1][0].get_motor_collection().name,
                "pipeline": [
                    {"$match": all[1][1][0].find_one(all[1][1][1]).get_filter_query()},
                    {"$limit": 1},
                    {
                        "$project": {
                            "_id": 0,
                            "kind": {"$literal": all[1][0]},
                            "doc": "$$ROOT",
                        }
                    },
                ],
            }
        },
    ]

    found: dict[str, Any] = {query_info[0]: None for query_info in all}

    for row in all[0][1][0].get_motor_collection().aggregate(pipeline):
        model_info = queries.get(row["kind"])
        if model_info:
            found[row["kind"]] = model_info[0].model_validate(row["doc"])

    return found
