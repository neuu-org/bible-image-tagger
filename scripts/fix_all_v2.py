"""
Comprehensive fix script for all 1000 tagged images.
Fixes: OSIS refs, empty events, non-biblical primary refs, tag contamination,
missing reason/symbols, period mismatches, character names, malformed refs, kebab tags.
"""
import json, glob, os, re

os.chdir('C:/Users/Iury Coelho/Desktop/bible-image-tagger/data/output')

# === FIX 1: OSIS abbreviation mapping (includes batch 009 short codes) ===
OSIS_MAP = {
    # Standard long-form
    'Gen':'GEN','Exod':'EXO','Exo':'EXO','Lev':'LEV','Num':'NUM','Deut':'DEU','Deu':'DEU',
    'Josh':'JOS','Judg':'JDG','Ruth':'RUT','Rut':'RUT',
    '1Sam':'1SA','2Sam':'2SA','1Kgs':'1KI','2Kgs':'2KI','1Chr':'1CH','2Chr':'2CH',
    'Ezra':'EZR','Neh':'NEH','Esth':'EST','Job':'JOB',
    'Ps':'PSA','PS':'PSA','Psa':'PSA','Pss':'PSA','Psalm':'PSA',
    'Prov':'PRO','Pro':'PRO','Eccl':'ECC','Song':'SNG','Isa':'ISA',
    'Jer':'JER','Lam':'LAM','Ezek':'EZK','Ezk':'EZK','Dan':'DAN',
    'Hos':'HOS','Joel':'JOE','Amos':'AMO','Obad':'OBA','Jonah':'JON','Jon':'JON',
    'Mic':'MIC','Nah':'NAH','Hab':'HAB','Zeph':'ZEP','Hag':'HAG',
    'Zech':'ZEC','Zec':'ZEC','Mal':'MAL',
    'Matt':'MAT','Mat':'MAT','Mark':'MRK','Mrk':'MRK',
    'Luke':'LUK','Luk':'LUK','John':'JHN','Jhn':'JHN',
    'Acts':'ACT','Act':'ACT','Rom':'ROM',
    '1Cor':'1CO','2Cor':'2CO','1COR':'1CO','2COR':'2CO',
    'Gal':'GAL','Eph':'EPH','Phil':'PHP','Php':'PHP',
    'Col':'COL','1Thess':'1TH','2Thess':'2TH','1Th':'1TH','2Th':'2TH',
    '1Tim':'1TI','2Tim':'2TI','1Ti':'1TI','2Ti':'2TI',
    'Tit':'TIT','Phlm':'PHM','Phm':'PHM',
    'Heb':'HEB','Jas':'JAS','Jam':'JAS',
    '1Pet':'1PE','2Pet':'2PE','1Pe':'1PE','2Pe':'2PE',
    '1John':'1JN','2John':'2JN','3John':'3JN','1Jn':'1JN','2Jn':'2JN','3Jn':'3JN',
    'Jude':'JUD','Jud':'JUD','Rev':'REV',
    # Batch 009 short codes
    'MT':'MAT','MK':'MRK','LK':'LUK','JN':'JHN',
    'IS':'ISA','RV':'REV','RM':'ROM','GL':'GAL',
    'GN':'GEN','PR':'PRO','AC':'ACT','CL':'COL',
    'SS':'SNG','HO':'HOS','JD':'JUD','ES':'EST',
    'TB':'TOB','1SM':'1SA','JNH':'JON','2CHR':'2CH','JOL':'JOE',
}

VALID_BOOKS = {
    'GEN','EXO','LEV','NUM','DEU','JOS','JDG','RUT','1SA','2SA','1KI','2KI',
    '1CH','2CH','EZR','NEH','EST','JOB','PSA','PRO','ECC','SNG','ISA','JER',
    'LAM','EZK','DAN','HOS','JOE','AMO','OBA','JON','MIC','NAH','HAB','ZEP',
    'HAG','ZEC','MAL','MAT','MRK','LUK','JHN','ACT','ROM','1CO','2CO','GAL',
    'EPH','PHP','COL','1TH','2TH','1TI','2TI','TIT','PHM','HEB','JAS','1PE',
    '2PE','1JN','2JN','3JN','JUD','REV',
    'SIR','JDT','TOB','WIS','1MA','2MA','BAR',  # deuterocanonical OK
}

# === FIX 4: Period corrections ===
PERIOD_FIXES_BY_KEY = {
    '0060696': 'Exodus',       # Moses breaks tablets
    '0060817': 'Patriarchal',  # Sacrifice of Isaac
    '0030557': 'Exodus',       # Golden Calf
    '0030579': 'Patriarchal',  # Sacrifice of Isaac
    '0030774': 'Antediluvian', # Noah's Ark
    '0040457': 'Antediluvian', # After the Flood
    '0050076': 'Exodus',       # Moses with Tablets
    '0050691': 'Creation',     # Fall of Man
    '0040565': 'Gospel',       # Boy Jesus in Temple
    '0011081': 'Creation',     # Adam and Eve in Garden
}

PERIOD_NORMALIZATIONS = {
    'New Testament':'Gospel','Old Testament':'Monarchy','Passion':'Gospel',
    'Apostolic Age':'Apostolic','Primeval':'Creation','Judges':'Conquest',
    'United Monarchy':'Monarchy','Extra-Biblical':'Non-biblical','Modern':'Non-biblical',
    'Apocalyptic':'Eschatological','Early Church':'Apostolic',
    'Deuterocanonical':'Intertestamental','Second Temple':'Intertestamental',
    'Church History':'Non-biblical','Hagiographic':'Non-biblical',
    'Post-Biblical':'Non-biblical',
}

# === FIX 5: Character name normalization ===
CHAR_NORM = {
    'Jesus':'Jesus Christ','Christ':'Jesus Christ','Christ Child':'Jesus Christ',
    'Infant Jesus':'Jesus Christ','The Christ Child':'Jesus Christ',
    'Baby Jesus':'Jesus Christ','The Infant Christ':'Jesus Christ',
    'Risen Christ':'Jesus Christ','Dead Christ':'Jesus Christ',
    'The Virgin Mary':'Virgin Mary','The Virgin':'Virgin Mary',
    'Madonna':'Virgin Mary','Our Lady':'Virgin Mary','Mary':'Virgin Mary',
    'Angel Gabriel':'Gabriel','Archangel Gabriel':'Gabriel',
    'Three Magi':'Magi','The Magi':'Magi','Three Kings':'Magi',
    'Saint John the Baptist':'John the Baptist',
    'St. John the Baptist':'John the Baptist',
    'The Baptist':'John the Baptist',
    'Saint Peter':'Peter','St. Peter':'Peter','Simon Peter':'Peter','Apostle Peter':'Peter',
    'Saint Paul':'Paul','St. Paul':'Paul','Apostle Paul':'Paul',
    'Saint Jerome':'Jerome','St. Jerome':'Jerome',
    'Saint Stephen':'Stephen','St. Stephen':'Stephen',
    'Saint Joseph':'Joseph','St. Joseph':'Joseph',
    'Infant Saint John':'Infant John the Baptist',
    'Infant St. John':'Infant John the Baptist',
    'Young Saint John the Baptist':'Infant John the Baptist',
    'Infant Saint John the Baptist':'Infant John the Baptist',
    'Saint Mary Magdalene':'Mary Magdalene','St. Mary Magdalene':'Mary Magdalene',
    'The Magdalene':'Mary Magdalene','Magdalene':'Mary Magdalene',
    'Saint Thomas':'Thomas','St. Thomas':'Thomas',
    'Saint Matthew':'Matthew','St. Matthew':'Matthew',
    'Saint Mark':'Mark','St. Mark':'Mark',
    'Saint Luke':'Luke','St. Luke':'Luke',
    'Saint John the Evangelist':'John the Evangelist',
    'St. John the Evangelist':'John the Evangelist',
    'Saint Andrew':'Andrew','St. Andrew':'Andrew',
    'Saint Francis':'Francis of Assisi','St. Francis':'Francis of Assisi',
    'Saint Sebastian':'Sebastian','St. Sebastian':'Sebastian',
    'Saint Catherine':'Catherine of Alexandria','St. Catherine':'Catherine of Alexandria',
    'Saint Barbara':'Barbara','St. Barbara':'Barbara',
    'Saint Nicholas':'Nicholas','St. Nicholas':'Nicholas',
    'Saint Michael':'Archangel Michael',
    'God':'God the Father',
}

# === FIX 6: Art-style tags to remove ===
ART_TAGS_EXACT = {
    'baroque','renaissance','gothic','impressionism','expressionism','cubism',
    'surrealism','neoclassicism','romanticism','mannerism','art-deco','art-nouveau',
    'minimalism','pop-art','realism','pointillism','photorealism',
    'abstract-expressionism','symbolism','pre-raphaelite','counter-reformation',
    'fresco','engraving','watercolor','etching','woodcut','tempera','oil-painting',
    'grisaille','gold-leaf','plein-air','charcoal-drawing','pen-and-ink',
    'ink-drawing','pencil-drawing','chalk-drawing','mosaic','relief','sculpture',
    'icon-painting','sacra-conversazione','chiaroscuro','trompe-loeil',
    'sfumato','tenebrism','impasto','illuminated-manuscript',
    'altarpiece','triptych','diptych','lunette','predella','polyptych',
    'stained-glass','altarpiece-panel',
}

# Artist names that might appear as tags
ARTIST_TAGS = {
    'perugino','bosch','fra-angelico','rubens','caravaggio','tintoretto',
    'cranach','procaccini','michelangelo','raphael','titian','giotto',
    'rembrandt','velazquez','el-greco','murillo','zurbaran','dore',
    'tissot','mantegna','memling','bellini','lippi','signorelli',
}

# Compound art tags (substring match)
ART_SUBSTRINGS = [
    'venetian-renaissance','northern-renaissance','flemish-','dutch-',
    'spanish-painting','german-painting','byzantine-style',
    'sistine-chapel','orvieto-cathedral','st-marks-basilica',
    'vatican','palazzo-','cornaro-chapel','lund-cathedral',
    '-fresco','-engraving','-watercolor','-etching',
    'historiated-initial','di-sotto-in-su','heavy-impasto',
]

# === FIX 7: Character type fixes ===
TYPE_FIXES = {
    'DIVINE':'DEITY','ANIMAL':'OTHER','HOLY_FIGURE':'PERSON',
    'APOSTLE':'PERSON','PROPHET':'PERSON',
}

# ============ PROCESSING ============

stats = {
    'osis_fixed': 0, 'events_filled': 0, 'primary_downgraded': 0,
    'tags_removed': 0, 'tags_kebab': 0, 'reasons_added': 0,
    'symbols_added': 0, 'periods_fixed': 0, 'chars_normalized': 0,
    'refs_reformatted': 0, 'types_fixed': 0, 'desc_trimmed': 0,
    'theol_trimmed': 0, 'mood_trimmed': 0, 'total_files': 0,
}

for f in sorted(glob.glob('*.json')):
    with open(f, 'r', encoding='utf-8') as fh:
        d = json.load(fh)
    changed = False
    key = f.replace('.json', '')

    # FIX 1: OSIS refs
    for ref in d.get('scripture_refs', []):
        r = ref.get('ref', '')
        parts = r.split('.')
        if len(parts) >= 2:
            book = parts[0]
            # Direct mapping
            if book in OSIS_MAP:
                parts[0] = OSIS_MAP[book]
                ref['ref'] = '.'.join(parts)
                stats['osis_fixed'] += 1; changed = True
            # Case fix (e.g., "Gen" -> "GEN" if valid)
            elif book.upper() in VALID_BOOKS and book != book.upper():
                parts[0] = book.upper()
                ref['ref'] = '.'.join(parts)
                stats['osis_fixed'] += 1; changed = True

        # FIX 9: Fix malformed dual-format ranges (MAT.28.18-Matt.28.20 -> MAT.28.18-20)
        r = ref.get('ref', '')
        if '-' in r:
            left, right = r.split('-', 1)
            if '.' in right and len(right.split('.')) >= 3:
                # e.g., MAT.28.18-Matt.28.20 -> keep only the verse from right
                right_parts = right.split('.')
                if len(right_parts) >= 3:
                    ref['ref'] = left + '-' + right_parts[-1]
                    stats['refs_reformatted'] += 1; changed = True

        # FIX 5: Add missing reason field
        if 'reason' not in ref:
            ref['reason'] = ''
            stats['reasons_added'] += 1; changed = True

    # FIX 3: Downgrade "primary" to "typological" on Non-biblical images
    if d.get('period') == 'Non-biblical':
        for ref in d.get('scripture_refs', []):
            if ref.get('relevance') == 'primary':
                ref['relevance'] = 'typological'
                stats['primary_downgraded'] += 1; changed = True

    # FIX 2: Fill empty events from title
    ev = d.get('event', '').strip()
    if not ev:
        title = d.get('_meta', {}).get('title', '')
        if title:
            d['event'] = title
            stats['events_filled'] += 1; changed = True

    # FIX 4a: Period fixes by key
    if key in PERIOD_FIXES_BY_KEY:
        if d.get('period') != PERIOD_FIXES_BY_KEY[key]:
            d['period'] = PERIOD_FIXES_BY_KEY[key]
            stats['periods_fixed'] += 1; changed = True

    # FIX 4b: Period normalizations
    p = d.get('period', '')
    if p in PERIOD_NORMALIZATIONS:
        d['period'] = PERIOD_NORMALIZATIONS[p]
        stats['periods_fixed'] += 1; changed = True

    # FIX 5: Character name normalization
    for c in d.get('characters', []):
        if isinstance(c, dict):
            name = c.get('name', '')
            if name in CHAR_NORM:
                c['name'] = CHAR_NORM[name]
                stats['chars_normalized'] += 1; changed = True

    # FIX 7: Character type fixes
    for c in d.get('characters', []):
        if isinstance(c, dict) and c.get('type', '') in TYPE_FIXES:
            c['type'] = TYPE_FIXES[c['type']]
            stats['types_fixed'] += 1; changed = True

    # FIX 6a: Remove exact art-style tags
    tags = d.get('tags', [])
    clean_tags = []
    for tag in tags:
        t_lower = tag.lower().strip().replace(' ', '-')
        if t_lower in ART_TAGS_EXACT or t_lower in ARTIST_TAGS:
            stats['tags_removed'] += 1; changed = True
            continue
        # Check substring matches
        removed = False
        for sub in ART_SUBSTRINGS:
            if sub in t_lower:
                stats['tags_removed'] += 1; changed = True
                removed = True
                break
        if not removed:
            clean_tags.append(t_lower)
    d['tags'] = clean_tags

    # FIX 6b: Kebab-case enforcement
    new_tags = []
    for tag in d['tags']:
        # Remove apostrophes, accents, periods in tags
        fixed = tag.lower().strip()
        fixed = fixed.replace("'", '').replace("'", '')
        fixed = fixed.replace('.', '').replace('/', '-')
        fixed = re.sub(r'[àáâã]', 'a', fixed)
        fixed = re.sub(r'[èéêë]', 'e', fixed)
        fixed = re.sub(r'[ìíîï]', 'i', fixed)
        fixed = re.sub(r'[òóôõ]', 'o', fixed)
        fixed = re.sub(r'[ùúûü]', 'u', fixed)
        fixed = fixed.replace(' ', '-').replace('_', '-')
        while '--' in fixed:
            fixed = fixed.replace('--', '-')
        fixed = fixed.strip('-')
        if fixed != tag:
            stats['tags_kebab'] += 1; changed = True
        new_tags.append(fixed)
    d['tags'] = new_tags

    # FIX 6c: Add symbols field if missing
    if 'symbols' not in d:
        d['symbols'] = []
        stats['symbols_added'] += 1; changed = True

    # FIX: Trim description > 600
    desc = d.get('description', '')
    if len(desc) > 600:
        t = desc[:600]
        lp = max(t.rfind('. '), t.rfind('.'))
        d['description'] = desc[:lp + 1] if lp > 300 else desc[:597] + '...'
        stats['desc_trimmed'] += 1; changed = True

    # FIX: Trim theological_description > 1500
    td = d.get('theological_description', '')
    if len(td) > 1500:
        t = td[:1500]
        lp = max(t.rfind('. '), t.rfind('.'))
        d['theological_description'] = td[:lp + 1] if lp > 1000 else td[:1497] + '...'
        stats['theol_trimmed'] += 1; changed = True

    # FIX: Trim mood > 4
    mood = d.get('mood', [])
    if len(mood) > 4:
        d['mood'] = mood[:4]
        stats['mood_trimmed'] += 1; changed = True

    if changed:
        with open(f, 'w', encoding='utf-8') as fh:
            json.dump(d, fh, indent=2, ensure_ascii=False)
        stats['total_files'] += 1

print("=== FIX ALL v2 RESULTS ===")
for k, v in sorted(stats.items()):
    print(f"  {k}: {v}")
print(f"\nTotal files modified: {stats['total_files']} / {len(glob.glob('*.json'))}")
