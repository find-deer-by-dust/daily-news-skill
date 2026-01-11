from NewsGetter import NewsGetter
import os
import json
from dotenv import load_dotenv

load_dotenv(override=True)
def main():
    users =  json.loads(os.getenv('users'))
    newsGetter = NewsGetter(7)
    newsGetter.sendNews(users)
    

if __name__ == "__main__":
    main()