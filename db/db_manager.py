from pymongo import MongoClient
import os

def get_mongo_collection(db_name: str, collection_name: str):
    """
    Returns a MongoDB collection object.
    """
    mongo_cluster = MongoClient(os.getenv("MONGO_CLUSTER_URI"))
    db = mongo_cluster[db_name]
    return db[collection_name]
