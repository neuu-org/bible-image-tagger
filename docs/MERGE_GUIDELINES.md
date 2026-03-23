# Guidelines for Merging Discovered Entities into Gazetteers

## Context

The image tagger discovers entities (characters, symbols, events) that don't exist
in the `bible-gazetteers-dataset`. These are exported as candidates by
`discovery_report.py`. **Not all candidates should be merged** — the gazetteers
dataset is specifically for **biblical entities**, not all of Christian history.

## Classification of Discovered Entities

### 1. Biblical entities (MERGE)
Entities that appear in Scripture but are missing from the gazetteers.

- Mary of Bethany, Martha of Bethany, Virgin Mary
- Nicodemus, Joseph of Arimathea, Barabbas
- Symbols: crown of thorns, thirty pieces of silver, burning bush

**Action**: Add to gazetteers with proper canonical_id, key_refs, and sources.

### 2. Post-biblical saints and historical figures (DO NOT MERGE)
Saints, martyrs, and historical figures not found in Scripture.

- Saint Secunda, Saint Rufina, Joan of Arc, Saint Gregory
- Church Fathers (as depicted subjects, not as sources)

**Action**: Keep in the image tagger output but do NOT add to the biblical gazetteers.
These could feed a separate "Christian figures" dataset in the future.

### 3. Generic visual descriptions (DO NOT MERGE)
Descriptive labels for unnamed figures in paintings.

- "Elderly Woman (servant)", "Young Woman (kitchen maid)"
- "Courtiers", "Attendants and handmaidens"
- "Naval combatants", "Travelers and townspeople"

**Action**: These are valid in the image tagger output for describing what's in
the painting, but they are NOT entities. Never merge into gazetteers.

### 4. Intertestamental / Deuterocanonical figures (REVIEW CASE BY CASE)
Figures from the deuterocanonical books or intertestamental period that may
or may not be in scope for the gazetteers.

- Antiochus IV Epiphanes (appears in Daniel 11, 1-2 Maccabees)
- Judas Maccabeus (1-2 Maccabees)
- Seleucus (historical, but referenced in Daniel's prophecies)

**Action**: Review against the gazetteers scope. If the figure has a direct
scriptural reference, consider adding. If purely historical, skip.

## Deduplication Risks

Before merging any candidate, check for existing entries under different names:

| Candidate | May already exist as |
|-----------|---------------------|
| Virgin Mary | PER:maria, PER:mary |
| Mary of Bethany | PER:mary (ambiguous — multiple Marys) |
| Christ Child | DIV:jesus, PER:jesus |
| Martha of Bethany | PER:martha |

Always search by aliases and fuzzy match before creating a new entry.

## Symbol Normalization

Opus generates enriched symbol names like `"chalice (Eucharistic cup, blood of Christ)"`.
Before merging symbols into gazetteers:

1. Extract the base name: `"chalice"`
2. Check if it exists: `OBJ:calice` (Portuguese) or similar
3. If it exists, add the English name as an alias
4. If it doesn't exist, create with proper Portuguese name + English alias
5. Opus-generated meanings can inform the `symbolic_meaning` field

## When to Run the Merge

- NOT during processing — focus on generating clean output JSONs first
- After reaching 200+ processed images, run `discovery_report.py` to get frequency data
- Entities with 3+ occurrences across different paintings are strong candidates
- Manual review is required — never auto-merge into gazetteers
