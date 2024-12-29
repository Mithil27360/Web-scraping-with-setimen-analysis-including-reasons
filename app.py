from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
from textblob import TextBlob
import traceback
from urllib.parse import urljoin

app = Flask(__name__)


def analyze_sentiment(headline):
    try:
        analysis = TextBlob(headline)
        polarity = analysis.sentiment.polarity

        if polarity > 0:
            impact = 'Positive'
            confidence = min(abs(polarity * 100) + 50, 100)
            explanation = "This headline shows positive sentiment due to its optimistic or favorable tone."
        elif polarity < 0:
            impact = 'Negative'
            confidence = min(abs(polarity * 100) + 50, 100)
            explanation = "This headline shows negative sentiment due to its pessimistic or unfavorable tone."
        else:
            impact = 'Neutral'
            confidence = 50
            explanation = "This headline appears to be neutral in tone."

        return impact, confidence, explanation
    except Exception as e:
        print(f"Error analyzing sentiment: {str(e)}")
        return 'Neutral', 50, 'Unable to analyze'


def extract_articles(url, page=1):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        # Handle pagination if the URL supports it
        if '?' in url:
            paginated_url = f"{url}&page={page}"
        else:
            paginated_url = f"{url}?page={page}"

        response = requests.get(paginated_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Look for common article container patterns
        article_containers = (
                soup.find_all('article') or
                soup.find_all('div', class_=['article', 'post', 'news-item']) or
                soup.find_all('div', {'data-testid': lambda x: x and 'article' in x.lower() if x else False})
        )

        articles = []
        seen_headlines = set()

        # First try to extract from article containers
        for container in article_containers:
            headline_elem = (
                    container.find(['h1', 'h2', 'h3']) or
                    container.find(class_=['headline', 'title'])
            )

            if headline_elem:
                headline = headline_elem.get_text(strip=True)
                link_elem = container.find('a')
                if link_elem and headline and len(headline) > 20 and headline not in seen_headlines:
                    link = urljoin(url, link_elem['href'])
                    seen_headlines.add(headline)
                    articles.append((headline, link))

        # If no articles found in containers, fall back to analyzing all links
        if not articles:
            for link in soup.find_all('a', href=True):
                headline = link.get_text(strip=True)
                if headline and len(headline) > 20 and headline not in seen_headlines:
                    full_link = urljoin(url, link['href'])
                    if full_link.startswith(('http://', 'https://')):
                        seen_headlines.add(headline)
                        articles.append((headline, full_link))

        return articles
    except Exception as e:
        print(f"Error extracting articles: {str(e)}")
        return []


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        url = request.json['url']
        page = request.json.get('page', 1)

        # Extract articles from multiple pages
        all_articles = []
        for p in range(page, page + 3):  # Get 3 pages worth of articles
            articles = extract_articles(url, p)
            all_articles.extend(articles)
            if len(all_articles) >= 30:  # Limit to 30 articles total
                break

        results = []
        for headline, link in all_articles[:30]:  # Process up to 30 articles
            impact, confidence, explanation = analyze_sentiment(headline)
            results.append({
                'headline': headline,
                'link': link,
                'impact': impact,
                'confidence': confidence,
                'explanation': explanation
            })

        return jsonify({
            'success': True,
            'results': results,
            'hasMore': len(all_articles) > 30
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    app.run(debug=True)