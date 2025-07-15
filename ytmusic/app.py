from ytmusicapi import YTMusic

def lambda_handler(event, context):
    title = event.get("title")
    author = event.get("author")

    if not title or not author:
        return {"statusCode": 400, "body": "Missing title or author"}

    ytmusic = YTMusic()
    results = ytmusic.search(query=f"{title} {author}", filter="songs")

    if not results:
        return {"statusCode": 404, "body": "Track not found"}

    track = results[0]
    return {
        "statusCode": 200,
        "body": {
            "title": track.get("title"),
            "artist": track.get("artists")[0].get("name"),
            "videoId": track.get("videoId"),
            "url": f"https://music.youtube.com/watch?v={track.get('videoId')}"
        }
    }

if __name__ == "__main__":
    import json
    event = {"title": "Verabo en NY", "author": "Toman"}
    print(json.dumps(lambda_handler(event, None), indent=2))
