import streamlit as st
import datetime
from collections import Counter, defaultdict
from googleapiclient.discovery import build

# Set your YouTube API key.
YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]  # or replace with your API key string

# Build the YouTube API client
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

def parse_iso_date(date_str):
    formats = ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Time data '{date_str}' does not match expected formats.")

def get_published_after(time_span: str) -> str:
    """
    Calculate the ISO 8601 formatted date string for the start date of the given time span.
    This threshold will be used to filter trending videos.
    """
    now = datetime.datetime.utcnow()
    if time_span == '1 Week':
        delta = datetime.timedelta(days=7)
    elif time_span == '1 Month':
        delta = datetime.timedelta(days=30)
    elif time_span == '6 Months':
        delta = datetime.timedelta(days=180)
    else:
        delta = datetime.timedelta(days=7)
    published_after = (now - delta).isoformat("T") + "Z"
    return published_after

def get_trending_topics(time_span: str, region: str):
    """
    Fetch trending videos (using the trending videos endpoint),
    filter them by the published date (based on the time span),
    group them by category, and return the top 10 categories (topics)
    along with a comment and a list of video titles.
    """
    published_after = get_published_after(time_span)
    # For region selection, use "BR" for Brazil and "US" for world trending.
    region_code = "BR" if region == "Brazil" else "US"
    
    try:
        # Fetch trending videos using the "mostPopular" chart.
        trending_response = youtube.videos().list(
            part="snippet",
            chart="mostPopular",
            regionCode=region_code,
            maxResults=50
        ).execute()
    except Exception as e:
        st.error(f"Error fetching trending videos: {e}")
        return []
    
    items = trending_response.get("items", [])
    if not items:
        st.info("No trending videos found for the selected region.")
        return []
    
    # Filter videos by published date (only include videos newer than our threshold).
    filtered_items = []
    try:
        threshold_date = parse_iso_date(published_after)
    except Exception as e:
        st.error(f"Error parsing threshold date: {e}")
        return []
    
    for item in items:
        published_at = item["snippet"].get("publishedAt")
        try:
            video_date = parse_iso_date(published_at)
        except Exception:
            continue
        if video_date >= threshold_date:
            filtered_items.append(item)
    
    if not filtered_items:
        st.info("No trending videos found for the selected time span and region.")
        return []
    
    # Group the filtered videos by category and collect their titles.
    category_counter = Counter()
    category_videos = defaultdict(list)
    
    for item in filtered_items:
        snippet = item.get("snippet", {})
        category_id = snippet.get("categoryId")
        title = snippet.get("title")
        if category_id and title:
            category_counter[category_id] += 1
            category_videos[category_id].append(title)
    
    if not category_counter:
        st.info("No category information found for the videos.")
        return []
    
    # Get the top 10 categories (most frequent)
    top_categories = category_counter.most_common(10)
    
    # Fetch the category names using the Video Categories API.
    category_ids_list = list(dict(top_categories).keys())
    try:
        categories_response = youtube.videoCategories().list(
            part="snippet",
            id=",".join(category_ids_list)
        ).execute()
    except Exception as e:
        st.error(f"Error fetching category details: {e}")
        return []
    
    category_mapping = {}
    for item in categories_response.get("items", []):
        cat_id = item["id"]
        cat_title = item["snippet"]["title"]
        category_mapping[cat_id] = cat_title
    
    # Build and return the list of topics with a comment and the list of video titles.
    topics = []
    for cat_id, count in top_categories:
        cat_name = category_mapping.get(cat_id, "Unknown")
        comment = f"There are {count} popular videos trending in the '{cat_name}' category during this period."
        videos = category_videos.get(cat_id, [])
        topics.append({"topic": cat_name, "comment": comment, "videos": videos})
    
    return topics

def main():
    st.title("YouTube Trends Explorer")
    st.write("Explore the top 10 trending topics on YouTube over different time spans and regions based on video categories.")

    # Sidebar controls for time span and region selection.
    st.sidebar.header("Configuration")
    time_span = st.sidebar.radio("Select Time Span:",
                                 ('1 Week', '1 Month', '6 Months'))
    region = st.sidebar.radio("Select Region:",
                              ('Brazil', 'World'))

    st.header(f"Trending Topics for the Past {time_span} ({region})")

    topics = get_trending_topics(time_span, region)

    if topics:
        for i, topic_data in enumerate(topics, start=1):
            st.subheader(f"{i}. {topic_data['topic']}")
            st.write(topic_data['comment'])
            if topic_data["videos"]:
                st.markdown("**Trending Video Titles:**")
                for title in topic_data["videos"]:
                    st.markdown(f"- {title}")
            st.markdown("---")
    else:
        st.write("No data available for the selected time span and region.")

    st.markdown("---")
    st.caption(f"Data last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
