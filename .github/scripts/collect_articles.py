#!/usr/bin/env python3
"""
아티클 수집 스크립트
GeekNews와 RSS 피드에서 최신 아티클을 수집합니다.
"""

import json
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import feedparser
from dateutil import parser as date_parser
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GITHUB_DIR = os.path.dirname(SCRIPT_DIR)
CANDIDATES_DIR = os.path.join(GITHUB_DIR, 'candidates')
PROCESSED_URLS_FILE = os.path.join(CANDIDATES_DIR, 'processed_urls.json')
COLLECTED_ARTICLES_FILE = os.path.join(CANDIDATES_DIR, 'collected_articles.json')

TRACKING_QUERY_KEYS = {
    'fbclid', 'gclid', 'mc_cid', 'mc_eid', 'ref', 'ref_src', 'source'
}


def ensure_candidates_dir():
    os.makedirs(CANDIDATES_DIR, exist_ok=True)


def normalize_url(url):
    """URL 정규화 (중복 제거를 위한 canonical URL 생성)"""
    if not url:
        return ""

    try:
        parsed = urlparse(url.strip())
        scheme = (parsed.scheme or 'https').lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip('/') or '/'

        query_pairs = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=False):
            key_lower = key.lower()
            if key_lower.startswith('utm_') or key_lower in TRACKING_QUERY_KEYS:
                continue
            query_pairs.append((key, value))

        query_pairs.sort(key=lambda x: (x[0], x[1]))
        query = urlencode(query_pairs, doseq=True)
        return urlunparse((scheme, netloc, path, '', query, ''))
    except Exception:
        return url.strip()


def normalize_title(title):
    """제목 정규화 (URL이 다르더라도 동일 아티클 감지)"""
    if not title:
        return ""
    lowered = title.lower().strip()
    cleaned = re.sub(r'[^\w가-힣]+', ' ', lowered)
    return re.sub(r'\s+', ' ', cleaned).strip()


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_datetime(value):
    if not value:
        return None
    try:
        return date_parser.parse(value)
    except (TypeError, ValueError):
        return None


def merge_articles(existing, incoming):
    """중복 아티클 병합: 더 풍부한 메타데이터를 유지"""
    merged = dict(existing)

    # URL은 canonical URL을 우선 사용
    existing_url = normalize_url(existing.get('url'))
    incoming_url = normalize_url(incoming.get('url'))
    if incoming_url and (not existing_url or len(incoming_url) > len(existing_url)):
        merged['url'] = incoming_url
    elif existing_url:
        merged['url'] = existing_url

    # 제목/요약은 더 긴 정보를 유지
    if len(incoming.get('title', '')) > len(existing.get('title', '')):
        merged['title'] = incoming.get('title', '')
    if len(incoming.get('summary', '')) > len(existing.get('summary', '')):
        merged['summary'] = incoming.get('summary', '')

    # 소셜 지표는 큰 값을 유지
    merged['upvotes'] = max(safe_int(existing.get('upvotes')), safe_int(incoming.get('upvotes')))
    merged['comments'] = max(safe_int(existing.get('comments')), safe_int(incoming.get('comments')))

    # 발행일은 최신 값을 유지
    existing_dt = parse_datetime(existing.get('published_at'))
    incoming_dt = parse_datetime(incoming.get('published_at'))
    if existing_dt and incoming_dt:
        merged['published_at'] = max(existing_dt, incoming_dt).isoformat()
    elif incoming_dt:
        merged['published_at'] = incoming_dt.isoformat()
    elif existing_dt:
        merged['published_at'] = existing_dt.isoformat()
    else:
        merged['published_at'] = incoming.get('published_at', existing.get('published_at', datetime.now().isoformat()))

    # 출처는 기존 값 유지 (평가 로직 호환)
    merged['source'] = existing.get('source') or incoming.get('source') or 'GeekNews'
    return merged


def deduplicate_articles(articles):
    """URL/제목 기반 중복 제거"""
    deduped = []
    url_index = {}
    title_index = {}

    for article in articles:
        normalized_url = normalize_url(article.get('url', ''))
        normalized_title = normalize_title(article.get('title', ''))

        article_copy = dict(article)
        if normalized_url:
            article_copy['url'] = normalized_url

        existing_idx = None
        if normalized_url and normalized_url in url_index:
            existing_idx = url_index[normalized_url]
        elif normalized_title and normalized_title in title_index:
            existing_idx = title_index[normalized_title]

        if existing_idx is None:
            deduped.append(article_copy)
            idx = len(deduped) - 1
            if normalized_url:
                url_index[normalized_url] = idx
            if normalized_title:
                title_index[normalized_title] = idx
        else:
            deduped[existing_idx] = merge_articles(deduped[existing_idx], article_copy)
            if normalized_url:
                url_index[normalized_url] = existing_idx
            if normalized_title:
                title_index[normalized_title] = existing_idx

    return deduped

def collect_geeknews(processed_urls):
    """GeekNews에서 최신 아티클 수집"""
    url = "https://news.hada.io"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        articles = []
        # 최신 50개 아티클 수집
        article_elements = soup.select('.topic_row')[:50]

        for elem in article_elements:
            try:
                # 제목과 링크
                title_elem = elem.select_one('.topic_title a')
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                raw_link = title_elem.get('href', '').strip()
                if not raw_link:
                    continue

                link = normalize_url(urljoin(url, raw_link))
                if link in processed_urls:
                    continue

                # 추천수
                upvotes = 0
                upvotes_elem = elem.select_one('.upvotes')
                if upvotes_elem:
                    upvotes_text = upvotes_elem.get_text(strip=True)
                    try:
                        upvotes = int(upvotes_text.split()[0])
                    except (ValueError, IndexError):
                        upvotes = 0

                # 댓글수
                comments = 0
                comments_elem = elem.select_one('.comments')
                if comments_elem:
                    comments_text = comments_elem.get_text(strip=True)
                    try:
                        comments = int(comments_text.split()[0])
                    except (ValueError, IndexError):
                        comments = 0

                # 발행일 (상대적 시간, 오늘 것으로 가정)
                published_at = datetime.now()

                # 요약 (제목 기반)
                summary = title[:100] + "..." if len(title) > 100 else title

                articles.append({
                    'title': title,
                    'url': link,
                    'upvotes': upvotes,
                    'comments': comments,
                    'published_at': published_at.isoformat(),
                    'summary': summary,
                    'source': 'GeekNews'
                })

            except Exception as e:
                print(f"Error parsing article: {e}")
                continue

        return articles

    except Exception as e:
        print(f"Error collecting from GeekNews: {e}")
        return []

def load_processed_urls():
    """이전에 처리된 URL 목록 로드"""
    ensure_candidates_dir()
    if os.path.exists(PROCESSED_URLS_FILE):
        try:
            with open(PROCESSED_URLS_FILE, 'r', encoding='utf-8') as f:
                return {normalize_url(url) for url in json.load(f) if normalize_url(url)}
        except Exception as e:
            print(f"Error loading processed URLs: {e}")
    return set()

def save_processed_urls(urls):
    """처리된 URL 목록 저장"""
    ensure_candidates_dir()
    try:
        normalized_urls = sorted({normalize_url(url) for url in urls if normalize_url(url)})
        with open(PROCESSED_URLS_FILE, 'w', encoding='utf-8') as f:
            json.dump(normalized_urls, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving processed URLs: {e}")

def scrape_geeknews_details(url):
    """GeekNews 상세 페이지에서 추천수와 댓글수 스크래핑"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # 추천수 추출: <span id='tp{id}'>숫자</span>
        upvotes = 0
        # URL에서 ID 추출
        url_match = re.search(r'id=(\d+)', url)
        if url_match:
            topic_id = url_match.group(1)
            upvotes_elem = soup.select_one(f'span#tp{topic_id}')
            if upvotes_elem:
                upvotes_text = upvotes_elem.get_text(strip=True)
                try:
                    upvotes = int(upvotes_text)
                except (ValueError, TypeError):
                    upvotes = 0

        # 댓글수 추출: "댓글 N개" 텍스트에서 추출
        comments = 0
        comments_elem = soup.find('a', string=re.compile(r'댓글\s+\d+개'))
        if comments_elem:
            comments_text = comments_elem.get_text(strip=True)
            comments_match = re.search(r'(\d+)개', comments_text)
            if comments_match:
                try:
                    comments = int(comments_match.group(1))
                except (ValueError, TypeError):
                    comments = 0

        return upvotes, comments

    except Exception as e:
        print(f"Error scraping details from {url}: {e}")
        return 0, 0

def collect_rss_articles(processed_urls):
    """GeekNews RSS에서 아티클 수집 - 개선된 버전"""
    geeknews_rss_url = "https://feeds.feedburner.com/geeknews-feed"

    try:
        feed = feedparser.parse(geeknews_rss_url)
        print(f"Found {len(feed.entries)} entries in GeekNews RSS")
    except Exception as e:
        print(f"Error parsing GeekNews RSS: {e}")
        return []

    articles = []
    now = datetime.now()
    cutoff_time = (now - timedelta(hours=6)).replace(tzinfo=None)

    for entry in feed.entries[:30]:  # 더 많은 항목 처리 (30개)
        try:
            link = normalize_url(entry.link)
            if not link:
                continue

            # URL 중복 체크
            if link in processed_urls:
                continue

            # 발행일 파싱
            published_at = None
            if hasattr(entry, 'published'):
                published_at = date_parser.parse(entry.published)
            elif hasattr(entry, 'updated'):
                published_at = date_parser.parse(entry.updated)
            else:
                continue

            published_at_naive = published_at.replace(tzinfo=None)
            if published_at_naive < cutoff_time:
                continue

            # 요약
            summary = ""
            if hasattr(entry, 'summary'):
                summary = entry.summary[:300] + "..." if len(entry.summary) > 300 else entry.summary
            elif hasattr(entry, 'description'):
                summary = entry.description[:300] + "..." if len(entry.description) > 300 else entry.description

            # 기본 아티클 정보
            article = {
                'title': entry.title,
                'url': link,
                'upvotes': 0,  # 기본값
                'comments': 0,  # 기본값
                'published_at': published_at.isoformat() if published_at else datetime.now().isoformat(),
                'summary': summary,
                'source': 'GeekNews'
            }

            # 품질 기반으로 상세 정보 스크래핑 결정
            # 제목에 기술 키워드가 있거나 구조화된 내용이면 상세 정보 수집
            should_scrape = False
            title_lower = entry.title.lower()
            tech_keywords = ['architecture', 'algorithm', 'performance', 'optimization',
                           'framework', 'library', 'api', 'database', 'ai', 'system']

            if any(keyword in title_lower for keyword in tech_keywords):
                should_scrape = True
            elif len(summary) > 200:  # 내용이 풍부한 경우
                should_scrape = True
            elif '•' in summary or '*' in summary or '1.' in summary:  # 구조화된 내용
                should_scrape = True

            # 상세 정보 스크래핑
            if should_scrape:
                upvotes, comments = scrape_geeknews_details(link)
                article['upvotes'] = upvotes
                article['comments'] = comments
                print(f"Scraped details for: {entry.title[:50]}... (👍{upvotes}, 💬{comments})")

            articles.append(article)

        except Exception as e:
            print(f"Error parsing RSS entry: {e}")
            continue

    print(f"Collected {len(articles)} new articles from RSS")
    return articles

def main():
    """메인 수집 함수"""
    print("Starting article collection...")
    ensure_candidates_dir()

    processed_urls = load_processed_urls()
    print(f"Loaded {len(processed_urls)} processed URLs")

    # GeekNews 수집
    geeknews_articles = collect_geeknews(processed_urls)
    print(f"Collected {len(geeknews_articles)} articles from GeekNews")

    # RSS 피드 수집
    rss_articles = collect_rss_articles(processed_urls)
    print(f"Collected {len(rss_articles)} articles from RSS feeds")

    # 모든 아티클 합치기
    all_articles = geeknews_articles + rss_articles
    deduped_articles = deduplicate_articles(all_articles)
    print(f"Deduplicated {len(all_articles)} -> {len(deduped_articles)} articles")

    # 처리된 URL 목록 업데이트
    new_urls = {
        normalize_url(article.get('url', ''))
        for article in deduped_articles
        if normalize_url(article.get('url', ''))
    }
    processed_urls.update(new_urls)
    save_processed_urls(processed_urls)
    print(f"Updated processed URLs count: {len(processed_urls)}")

    # 저장
    with open(COLLECTED_ARTICLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(deduped_articles, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(deduped_articles)} articles to {COLLECTED_ARTICLES_FILE}")

if __name__ == "__main__":
    main()
