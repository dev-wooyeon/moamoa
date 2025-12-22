#!/usr/bin/env python3
"""
PR 생성 스크립트
점수가 높은 후보 아티클에 대해 PR을 생성합니다.
"""

import json
import os
from datetime import datetime
import subprocess
import re

# 주제별 키워드 매핑
TOPIC_KEYWORDS = {
    'architecture': ['architecture', 'hexagonal', 'clean', 'ddd', 'domain driven', 'cqrs', 'event sourcing'],
    'backend': ['spring', 'backend', 'database', 'sql', 'nosql', 'api', 'rest', 'graphql', 'microservice', 'server'],
    'ai': ['ai', 'artificial intelligence', 'machine learning', 'ml', 'deep learning', 'neural', 'model', 'nlp', 'computer vision'],
    'frontend': ['react', 'vue', 'angular', 'javascript', 'frontend', 'ui', 'ux', 'web', 'html', 'css'],
    'devops': ['docker', 'kubernetes', 'ci/cd', 'jenkins', 'github actions', 'devops', 'infrastructure', 'cloud', 'aws', 'azure'],
    'testing': ['test', 'testing', 'tdd', 'bdd', 'quality', 'refactor', 'code review', 'coverage'],
    'system_design': ['system design', 'scalability', 'distributed', 'load balancing', 'caching', 'concurrency'],
    'career': ['career', 'growth', 'learning', 'interview', 'skill', 'soft skill', 'communication']
}

TOPIC_NAMES = {
    'architecture': '🏗️ 아키텍처 & 설계',
    'backend': '💻 백엔드 개발',
    'ai': '🤖 AI & 머신러닝',
    'frontend': '📱 프론트엔드',
    'devops': '🔧 데브옵스 & 시스템',
    'testing': '🧪 테스트 & 품질',
    'system_design': '📈 시스템 디자인',
    'career': '🌱 개발자 성장'
}

def classify_topic(article):
    """아티클을 주제별로 분류"""
    title = article['title'].lower()
    url = article.get('url', '').lower()
    text_to_check = title + ' ' + url

    topic_scores = {}

    for topic, keywords in TOPIC_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword.lower() in text_to_check:
                score += 1
        if score > 0:
            topic_scores[topic] = score

    if topic_scores:
        # 가장 높은 점수의 주제를 선택
        best_topic = max(topic_scores, key=topic_scores.get)
        return best_topic

    return 'career'  # 기본값은 career로 설정

def create_markdown_content(candidates, source_type):
    """마크다운 콘텐츠 생성 - 주제별로 분류"""
    today = datetime.now().strftime('%Y-%m-%d')

    content = f"# 아티클 후보 - {today}\n\n"
    content += f"출처: {source_type}\n\n"
    content += "아티클들은 주제별로 자동 분류되었으며, 각 주제 내에서 점수별로 정렬됩니다.\n\n"

    # 주제별로 후보 분류
    topic_candidates = {}
    for candidate in candidates:
        article = candidate['article']
        topic = classify_topic(article)
        if topic not in topic_candidates:
            topic_candidates[topic] = []
        topic_candidates[topic].append(candidate)

    # 각 주제별로 처리
    for topic_key in sorted(topic_candidates.keys(), key=lambda x: list(TOPIC_NAMES.keys()).index(x)):
        topic_name = TOPIC_NAMES[topic_key]
        candidates_in_topic = topic_candidates[topic_key]

        content += f"## {topic_name}\n\n"

        # 점수별 분류
        high_score = [c for c in candidates_in_topic if c['score'] >= 80]
        medium_score = [c for c in candidates_in_topic if 60 <= c['score'] < 80]

        if high_score:
            content += "### ⭐ 추천 아티클 (점수 ≥ 80)\n\n"
            for candidate in sorted(high_score, key=lambda x: x['score'], reverse=True):
                article = candidate['article']
                breakdown = candidate['breakdown']

                content += f"#### {article['title']}\n"
                content += f"**점수:** {candidate['score']} | **출처:** {article['source']} | **발행:** {article['published_at'][:10]}\n\n"

                content += "🔍 **평가 상세:**\n"
                content += f"- 기본 점수: +{breakdown['base']}\n"
                content += f"- 제목 품질: +{breakdown['title_quality']}\n"
                content += f"- 내용 깊이: +{breakdown['content_depth']}\n"
                content += f"- 실용성: +{breakdown['practicality']}\n"
                content += f"- 주제 적합성: +{breakdown['topic_relevance']}\n"
                content += f"- 최신성: +{breakdown['recency']}\n"
                content += f"- 소셜 점수: +{breakdown['social_score']}\n"
                content += f"- 패널티: {breakdown['penalty']}\n\n"

                content += f"📎 **링크:** [{article['url']}]({article['url']})\n\n"

                content += "✅ **선정 이유:**\n"
                reasons = []
                if breakdown['upvotes'] > 0:
                    reasons.append(f"- GeekNews에서 {breakdown['upvotes']}점 추천")
                if breakdown['comments'] > 0:
                    reasons.append(f"- {breakdown['comments']}개의 댓글")
                if breakdown['recency'] > 0:
                    reasons.append("- 최근 24시간 내 발행")
                if breakdown['topic_relevance'] > 0:
                    reasons.append("- 개발 관련 주제")
                if breakdown['practicality'] > 0:
                    reasons.append("- 실용적인 내용 포함")
                if not reasons:
                    reasons.append("- 평가 기준 만족")

                for reason in reasons:
                    content += f"{reason}\n"
                content += "\n---\n\n"

        if medium_score:
            content += "### 📋 후보 아티클 (점수 60-79)\n\n"
            for candidate in sorted(medium_score, key=lambda x: x['score'], reverse=True):
                article = candidate['article']
                content += f"- [{article['title']}]({article['url']}) - 점수: {candidate['score']}\n"
                content += f"  - 출처: {article['source']}\n"
                content += f"  - 발행: {article['published_at'][:10]}\n\n"

        if not high_score and not medium_score:
            content += "_이 주제에 해당하는 후보 아티클이 없습니다._\n\n"

    content += "---\n\n"
    content += "📝 **검토 가이드**\n\n"
    content += "- ⭐ 표시된 아티클들은 고품질로 판단되며, 검토 후 `아티클/GeekNews.md`에 추가를 추천합니다.\n"
    content += "- 각 아티클의 주제 분류는 자동으로 이루어지며, 필요시 수동 조정이 가능합니다.\n"
    content += "- PR 승인 후 아티클들은 해당 주제 섹션에 추가됩니다.\n\n"

    content += "Human review required before archiving."

    return content

def create_pr_for_candidates(candidates, source_type):
    """후보 아티클에 대한 PR 생성"""
    if not candidates:
        print(f"No candidates for {source_type}")
        return

    today = datetime.now().strftime('%Y-%m-%d')
    filename = f"{today}-{source_type.lower()}.md"

    # 마크다운 파일 생성
    content = create_markdown_content(candidates, source_type)

    output_dir = os.path.join(os.path.dirname(__file__), '..', 'candidates')
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Created {filepath} with {len(candidates)} candidates")

    # GitHub CLI를 사용한 PR 생성 (점수 50 이상인 경우)
    high_score_candidates = [c for c in candidates if c['score'] >= 50]
    if high_score_candidates:
        try:
            # GitHub CLI 설치 확인
            result = subprocess.run(['which', 'gh'], capture_output=True, text=True)
            if result.returncode != 0:
                print("GitHub CLI (gh) not found. Skipping PR creation.")
                print("In GitHub Actions environment, this will work automatically.")
                return

            # Git 설정
            subprocess.run(['git', 'config', '--global', 'user.name', 'github-actions[bot]'], check=True)
            subprocess.run(['git', 'config', '--global', 'user.email', 'github-actions[bot]@users.noreply.github.com'], check=True)

            # 프로젝트 루트 디렉토리로 이동하여 git 작업 수행
            project_root = os.path.join(os.path.dirname(__file__), '..', '..')
            original_cwd = os.getcwd()

            try:
                os.chdir(project_root)
                print(f"Changed working directory to: {project_root}")

                # 새 브랜치 생성 및 체크아웃
                branch_name = f'article-candidates-{today}-{source_type.lower()}'
                subprocess.run(['git', 'checkout', '-b', branch_name], check=True)
                print(f"Created and switched to branch: {branch_name}")

                # 파일 추가 및 커밋 (루트 기준 상대 경로 사용)
                relative_filepath = os.path.relpath(filepath, project_root)
                subprocess.run(['git', 'add', relative_filepath], check=True)
                commit_message = f"Add article candidates - {today} ({source_type})"
                subprocess.run(['git', 'commit', '-m', commit_message], check=True)
                print(f"Committed changes: {commit_message}")

            finally:
                # 원래 디렉토리로 복귀
                os.chdir(original_cwd)

            # PR 생성
            pr_title = f"📚 아티클 후보 제안 - {today} ({source_type})"
            pr_body = f"자동으로 수집된 {source_type} 아티클 후보입니다.\n\n점수 50 이상인 아티클들은 검토 후 아카이브에 추가해 주세요."

            result = subprocess.run([
                'gh', 'pr', 'create',
                '--title', pr_title,
                '--body', pr_body,
                '--base', 'main',
                '--head', branch_name
            ], capture_output=True, text=True, check=True)

            print(f"Created PR: {result.stdout.strip()}")

        except subprocess.CalledProcessError as e:
            print(f"Error creating PR: {e}")
            print("This is expected in local environment. In GitHub Actions, PR will be created automatically.")
        except FileNotFoundError as e:
            print(f"GitHub CLI not found: {e}")
            print("This script is designed to run in GitHub Actions environment.")
    else:
        print(f"No high-score candidates (>= 50) for {source_type}, skipping PR creation")

def main():
    """메인 PR 생성 함수"""
    print("Starting PR creation...")

    # 후보 파일 로드
    candidates_file = os.path.join(os.path.dirname(__file__), '..', 'candidates', 'candidates.json')

    if not os.path.exists(candidates_file):
        print(f"Candidates file not found: {candidates_file}")
        return

    try:
        with open(candidates_file, 'r', encoding='utf-8') as f:
            candidates = json.load(f)
    except Exception as e:
        print(f"Error loading candidates: {e}")
        return

    # 출처별 분류
    geeknews_candidates = [c for c in candidates if c['article']['source'] == 'GeekNews']
    rss_candidates = [c for c in candidates if c['article']['source'] != 'GeekNews']

    print(f"Processing {len(geeknews_candidates)} GeekNews candidates")
    print(f"Processing {len(rss_candidates)} RSS candidates")

    # GeekNews 후보 PR 생성
    if geeknews_candidates:
        create_pr_for_candidates(geeknews_candidates, "geeknews")

    # RSS 후보 PR 생성
    if rss_candidates:
        create_pr_for_candidates(rss_candidates, "articles")

    print("PR creation completed")

if __name__ == "__main__":
    main()
