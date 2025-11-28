def rank_articles(articles):
    """
    Ritorna le 15 migliori notizie.
    Priorità:
    1) Fonti più autorevoli (lista interna)
    2) Lunghezza contenuto (contenuti più ricchi)
    3) Parole chiave tech rilevanti
    """

    authoritative_sources = [
        "TechCrunch", "The Verge", "Wired", "Ars Technica",
        "Light Reading", "Telecoms.com", "Fierce Telecom",
        "Data Center Knowledge", "MIT Technology Review",
        "Space News", "Advanced Television"
    ]

    keywords = [
        "ai", "5g", "fiber", "cloud", "satellite", "robot", 
        "telco", "data", "gen ai", "infrastructure", "broadcast",
        "edge", "quantum"
    ]

    def score(article):
        score = 0

        # Fonte autorevole
        for s in authoritative_sources:
            if s.lower() in article.source.lower():
                score += 50
                break

        # Lunghezza contenuto
        score += min(len(article.content) // 200, 50)

        # Parole chiave tecnologiche
        text = article.content.lower()
        score += sum(5 for k in keywords if k in text)

        return score

    ranked = sorted(articles, key=score, reverse=True)
    return ranked[:15]
