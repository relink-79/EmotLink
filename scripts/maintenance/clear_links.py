import sys
from pymongo import MongoClient

MONGO_URI = 'mongodb://localhost:27017/'
DB_NAME = 'emotlink_db'
COLLECTION = 'links'


def main():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    links = db[COLLECTION]

    # Show counts before
    before = links.count_documents({})
    print(f"[links] documents before: {before}")

    if '--drop' in sys.argv:
        links.drop()
        print("Dropped collection 'links'. It will be re-created automatically when new links are inserted.")
        after = 0
    else:
        result = links.delete_many({})
        print(f"Deleted {result.deleted_count} document(s) from 'links'.")
        after = links.count_documents({})

    print(f"[links] documents after: {after}")


if __name__ == '__main__':
    main()
