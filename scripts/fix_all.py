import json, glob, os

os.chdir('C:/Users/Iury Coelho/Desktop/bible-image-tagger/data/output')

# FIX 1: OSIS abbreviation mapping
osis_map = {
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
}

VALID_BOOKS = {
    'GEN','EXO','LEV','NUM','DEU','JOS','JDG','RUT','1SA','2SA','1KI','2KI',
    '1CH','2CH','EZR','NEH','EST','JOB','PSA','PRO','ECC','SNG','ISA','JER',
    'LAM','EZK','DAN','HOS','JOE','AMO','OBA','JON','MIC','NAH','HAB','ZEP',
    'HAG','ZEC','MAL','MAT','MRK','LUK','JHN','ACT','ROM','1CO','2CO','GAL',
    'EPH','PHP','COL','1TH','2TH','1TI','2TI','TIT','PHM','HEB','JAS','1PE',
    '2PE','1JN','2JN','3JN','JUD','REV',
    'SIR','JDT','TOB','WIS','1MA','2MA','BAR','SUS','BEL',  # deuterocanonical OK
}

# FIX 3: Period corrections
period_fixes = {
    '0030557': 'Exodus',
    '0030579': 'Patriarchal',
    '0030774': 'Antediluvian',
    '0040457': 'Antediluvian',
    '0050076': 'Exodus',
    '0050691': 'Creation',
    '0040565': 'Gospel',
    '0011081': 'Creation',  # Adam and Eve in Garden
}

# FIX 4: Character name normalization
char_norm = {
    'Jesus': 'Jesus Christ', 'Christ': 'Jesus Christ', 'Christ Child': 'Jesus Christ',
    'Infant Jesus': 'Jesus Christ', 'The Christ Child': 'Jesus Christ',
    'Baby Jesus': 'Jesus Christ', 'The Infant Christ': 'Jesus Christ',
    'Risen Christ': 'Jesus Christ', 'Dead Christ': 'Jesus Christ',
    'The Virgin Mary': 'Virgin Mary', 'The Virgin': 'Virgin Mary',
    'Madonna': 'Virgin Mary', 'Our Lady': 'Virgin Mary',
    'Angel Gabriel': 'Gabriel', 'Archangel Gabriel': 'Gabriel',
    'Three Magi': 'Magi', 'The Magi': 'Magi', 'Three Kings': 'Magi',
    'Saint John the Baptist': 'John the Baptist',
    'St. John the Baptist': 'John the Baptist',
    'The Baptist': 'John the Baptist',
    'Saint Peter': 'Peter', 'St. Peter': 'Peter', 'Simon Peter': 'Peter',
    'Saint Paul': 'Paul', 'St. Paul': 'Paul',
    'Saint Jerome': 'Jerome', 'St. Jerome': 'Jerome',
    'Saint Stephen': 'Stephen', 'St. Stephen': 'Stephen',
    'Saint Joseph': 'Joseph', 'St. Joseph': 'Joseph',
    'Infant Saint John': 'Infant John the Baptist',
    'Infant St. John': 'Infant John the Baptist',
    'Young Saint John the Baptist': 'Infant John the Baptist',
    'Infant Saint John the Baptist': 'Infant John the Baptist',
    'Saint Mary Magdalene': 'Mary Magdalene',
    'St. Mary Magdalene': 'Mary Magdalene',
    'The Magdalene': 'Mary Magdalene',
    'Magdalene': 'Mary Magdalene',
    'Saint Thomas': 'Thomas', 'St. Thomas': 'Thomas',
    'Saint Matthew': 'Matthew', 'St. Matthew': 'Matthew',
    'Saint Mark': 'Mark', 'St. Mark': 'Mark',
    'Saint Luke': 'Luke', 'St. Luke': 'Luke',
    'Saint John the Evangelist': 'John the Evangelist',
    'St. John the Evangelist': 'John the Evangelist',
    'Saint Andrew': 'Andrew', 'St. Andrew': 'Andrew',
    'Saint Catherine': 'Catherine of Alexandria',
    'St. Catherine': 'Catherine of Alexandria',
    'Saint Barbara': 'Barbara', 'St. Barbara': 'Barbara',
    'Saint Francis': 'Francis of Assisi', 'St. Francis': 'Francis of Assisi',
    'Saint Sebastian': 'Sebastian', 'St. Sebastian': 'Sebastian',
}

# FIX 6: Art-style tags to remove
art_tags_remove = {
    'fresco','engraving','watercolor','grisaille','gold-leaf','plein-air','woodcut',
    'etching','charcoal-drawing','pen-and-ink','oil-painting','tempera',
    'expressionism','expressionist','minimalism','pop-art','mannerist','neoclassical',
    'pointillism','photorealism','realism','art-nouveau','art-deco','abstract-expressionism',
    'sacra-conversazione','chiaroscuro','trompe-loeil',
    'sistine-chapel-ceiling','gallery-painting','imaginary-gallery',
    'copy-after-veronese','gustave-dore-engraving','baroque','renaissance','gothic',
    'impressionist','cubism','surrealism','neoclassicism','romanticism',
    'counter-reformation','venetian-painting','flemish-painting','dutch-painting',
    'spanish-painting','german-painting','northern-renaissance','pre-raphaelite',
    'mannerism','ink-drawing','pencil-drawing','chalk-drawing','illuminated-manuscript',
    'iconography','icon-painting','mosaic','relief','sculpture',
}

stats = {'osis': 0, 'kebab': 0, 'period': 0, 'charname': 0, 'arttag': 0,
         'theoldesc': 0, 'total_files': 0}

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
            if book in osis_map:
                parts[0] = osis_map[book]
                ref['ref'] = '.'.join(parts)
                stats['osis'] += 1
                changed = True
            elif book.upper() in VALID_BOOKS and book != book.upper():
                parts[0] = book.upper()
                ref['ref'] = '.'.join(parts)
                stats['osis'] += 1
                changed = True

    # FIX 2: Kebab-case tags
    new_tags = []
    for tag in d.get('tags', []):
        fixed = tag.lower().strip().replace(' ', '-').replace('_', '-')
        while '--' in fixed:
            fixed = fixed.replace('--', '-')
        fixed = fixed.strip('-')
        if fixed != tag:
            stats['kebab'] += 1
            changed = True
        new_tags.append(fixed)
    d['tags'] = new_tags

    # FIX 3: Period fixes
    if key in period_fixes:
        if d.get('period') != period_fixes[key]:
            d['period'] = period_fixes[key]
            stats['period'] += 1
            changed = True

    # FIX 4: Character name normalization
    for c in d.get('characters', []):
        if isinstance(c, dict):
            name = c.get('name', '')
            if name in char_norm:
                c['name'] = char_norm[name]
                stats['charname'] += 1
                changed = True

    # FIX 6: Remove art-style tags
    clean = [t for t in d['tags'] if t not in art_tags_remove]
    if len(clean) != len(d['tags']):
        stats['arttag'] += len(d['tags']) - len(clean)
        d['tags'] = clean
        changed = True

    # FIX 7: Trim theological_description > 1500
    td = d.get('theological_description', '')
    if len(td) > 1500:
        t = td[:1500]
        lp = max(t.rfind('. '), t.rfind('.'))
        if lp > 1000:
            d['theological_description'] = td[:lp + 1]
        else:
            d['theological_description'] = td[:1497] + '...'
        stats['theoldesc'] += 1
        changed = True

    if changed:
        with open(f, 'w', encoding='utf-8') as fh:
            json.dump(d, fh, indent=2, ensure_ascii=False)
        stats['total_files'] += 1

print("=== AUTO-FIX RESULTS ===")
for k, v in stats.items():
    print(f"  {k}: {v}")
