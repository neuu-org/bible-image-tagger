# bible-image-tagger

Pipeline para gerar tags bíblicas estruturadas em pinturas religiosas usando **Gemini 2 Flash Vision** e **embeddings multimodais**.

## Objetivo

Dado um dataset de 16.914 pinturas religiosas (WikiArt), gerar para cada imagem:

- **Personagens bíblicos** retratados
- **Evento/cena bíblica** representada
- **Referências OSIS** (e.g., `GEN.22.1-19`)
- **Testamento** (AT/NT)
- **Temas teológicos**
- **Símbolos visuais**

## Pipeline

```
00_raw (bible-images-dataset)
    │
    ├─► Fase 1: Gemini 2 Flash Vision → tags estruturadas por imagem
    ├─► Fase 2: Validação cruzada com gazetteers + topics
    ├─► Fase 3: Multimodal embeddings (imagem ↔ versículo)
    │
    ▼
output/ → JSON com tags por imagem + embeddings
```

## Stack

- **Python 3.12+**
- **Google Gemini 2 Flash** — tagging visual (multimodal)
- **Google Multimodal Embeddings** — busca semântica imagem↔texto
- Datasets de referência: `bible-gazetteers-dataset`, `bible-topics-dataset`, `bible-text-dataset`

## Estrutura

```
bible-image-tagger/
├── scripts/
│   ├── tag_images.py          # Pipeline principal de tagging com Gemini
│   ├── validate_tags.py       # Validação cruzada com gazetteers/topics
│   └── generate_embeddings.py # Embeddings multimodais
├── config/
│   └── settings.py            # Configurações e prompts
├── data/
│   ├── output/                # Tags geradas (JSON por imagem)
│   └── validation/            # Relatórios de validação
├── requirements.txt
└── README.md
```

## Uso

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar API key
export GOOGLE_API_KEY="your-key"

# Rodar tagging (batch)
python scripts/tag_images.py --input /path/to/bible-images-dataset --output data/output/

# Validar com gazetteers
python scripts/validate_tags.py --tags data/output/ --gazetteers /path/to/bible-gazetteers-dataset

# Gerar embeddings
python scripts/generate_embeddings.py --tags data/output/ --output data/embeddings/
```

## Custo estimado

| Fase | Modelo | Tokens estimados | Custo |
|------|--------|-----------------|-------|
| Tagging | Gemini 2 Flash | ~4.2M (imagens) + ~1.7M (prompts) | ~$0.50 |
| Embeddings | Multimodal Embedding | 16.914 imagens | ~$0.10 |
| **Total** | | | **~$0.60** |

## Licença

MIT
