"""Build a corpus-grounded slang dictionary without normalizing the tweets."""

import argparse
import collections
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request


HERE = Path(__file__).resolve().parent
OUTPUT = HERE.parent
SOURCE = OUTPUT / "MBG_Dataset_DirectReplies_20260907_0825_content_cleansing.csv"
DESTINATION = OUTPUT / "MBG_Kamus_Slang_Normalisasi_2000.csv"
TOKEN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")
FIELDS = ["slang", "kata_baku", "frekuensi"]
SOURCES = {
    "indocollex": (
        "https://raw.githubusercontent.com/haryoa/indo-collex/main/"
        "dict/inforformal-formal-Indonesian-dictionary.tsv"
    ),
    "salsabila": (
        "https://raw.githubusercontent.com/nasalsabila/kamus-alay/master/"
        "colloquial-indonesian-lexicon.csv"
    ),
}

# These terms have legitimate meanings that a context-free replacement would lose.
PROTECTED = set("""
mbg bgn sppg slhs haccp apbn apbd dpr dprd kpk bpom spp sd smp sma smk
sm s1 s2 s3 rt rw ri tni polri ppp pdi pkb pks pan psi pp ppn pph
si in to on of is as it at so no do go me my us we he be by an am
ai id dm pm am wa fb ig yt tv pc hp ac dc cv pt bu pak mas kak bang
hak kaya bisa beri hari tahu taiwan koi boros palu kali pas fit not
g d k n p r s t u v w x y z a b c e f h i j l m o q
dr cm mm kg km cc ml mk pd up rp usd ton gas tes net sos rs
bukan belum jangan tidak tanpa kurang
katanya makannya soalnya begitulah diubah kurangi pahami minta dibilang duluan
wo se tk pr ps gr if jk k3 kt rm su na pala see sk kk msk hr pk pkk sby
cs diksi hoaks keseringan mutualan nampak packing sharing tf tl br dd des
difoto gabut iii malang mboh mg pen planning students thailand tot ur
4th 5th aa asking apain eyes feels gets gg goals gunungkidul knows konsul
may mekdi mrs ntik pass pileg rabb sg slamet slm st takes takkan tt
travelling usa words 20th american anymore bagaimanapun barakallah bb
bm bronis called calls centre cong del details dies dj enakan failed
fi fruits gantian hands having hat hj hype instal jang jeung kana
keempat ketara kid lets mai means missed monday muaro needed nt nyalain
nyeplak ngiler op others paid php pkl ponsel prancis problems pu
rights segampang services shit skills skyline tb thoughts thousands
tools tracking week wanted wants yasinan nutrition indonesian
ngentot jancok fuck fak anjay anj njir njirrr anjirrrr ajig anjaaaayyyyyy
anjg ajg anying anjeng jing njing jirr njiirr nyet tay
dah dahh daah daahhhh daaah maneh kene zonk blusukan
bro ndut halu ma pa ka la ne bg say mang tah abs
koplak gokil
""".split())

# Canonical targets retain inflections, negation and evaluative meaning.
CANONICAL = {
    "enggak": "tidak", "nggak": "tidak", "ngga": "tidak", "gak": "tidak",
    "ga": "tidak", "kagak": "tidak", "kaga": "tidak", "ndak": "tidak",
    "kalo": "kalau", "kayak": "seperti", "gue": "saya", "gua": "saya",
    "lu": "kamu", "elo": "kamu", "elu": "kamu", "loe": "kamu",
    "pengin": "ingin", "pengen": "ingin", "pingin": "ingin",
    "entar": "nanti", "ntar": "nanti", "banget": "sangat", "tapi": "tetapi",
    "doang": "saja", "cuman": "hanya", "cuma": "hanya", "duit": "uang",
    "gimana": "bagaimana", "gitu": "begitu", "gini": "begini",
    "udah": "sudah", "bener": "benar", "beneran": "sungguh", "benaran": "sungguh",
    "bikin": "membuat", "ngomong": "berbicara", "mengomong": "berbicara",
    "mengasih": "memberi", "ngasih": "memberi", "dikasih": "diberi",
    "ngapain": "melakukan apa", "mengapai": "melakukan apa",
    "dapet": "dapat", "mending": "lebih baik", "mendingan": "lebih baik",
    "goblok": "goblok", "tolol": "tolol", "bego": "bodoh", "gila": "gila",
    "sensi": "sensitif", "cuek": "tidak peduli", "bete": "kesal",
    "cape": "capek", "capek": "lelah", "gimana": "bagaimana",
    "kangen": "rindu", "ngerti": "mengerti", "ngga": "tidak",
    "aja": "saja", "adek": "adik", "jaman": "zaman", "tau": "tahu",
    "nafas": "napas", "indak": "tidak", "dimana": "di mana",
    "disini": "di sini", "disana": "di sana", "kemana": "ke mana",
    "darimana": "dari mana", "diluar": "di luar", "ketawa": "tertawa",
    "cewek": "perempuan", "cowok": "laki-laki", "online": "daring",
    "tweet": "cuitan", "hahahaha": "hahaha", "mengakak": "tertawa terbahak-bahak",
    "handphone": "telepon seluler", "please": "tolong", "sukur": "syukur",
}

MANUAL_TEXT = """
yg|yang
aja|saja
kalo|kalau
klo|kalau
kl|kalau
dah|sudah
ni|ini
ngapain|melakukan apa
nanya|bertanya
nambah|menambah
bkn|bukan
mkn|makan
ngurusin|mengurusi
ngomong|berbicara
ngasih|memberi
ngasihnya|memberinya
lu|kamu
gue|saya
gua|saya
gw|saya
gwe|saya
elo|kamu
elu|kamu
loe|kamu
emang|memang
tau|tahu
banget|sangat
bgt|sangat
bikin|membuat
duit|uang
doang|saja
nggak|tidak
enggak|tidak
ndak|tidak
ndg|tidak
ndaklah|tidaklah
ndakbisa|tidak bisa
ndakada|tidak ada
ndakusah|tidak usah
gak|tidak
ga|tidak
gk|tidak
kagak|tidak
kaga|tidak
gini|begini
gitu|begitu
gimana|bagaimana
gmn|bagaimana
gmna|bagaimana
gimna|bagaimana
gmnana|bagaimana
gimanapun|bagaimanapun
gimananya|bagaimananya
gimanalah|bagaimanalah
ginian|seperti ini
gituan|seperti itu
segini|sebanyak ini
segitu|sebanyak itu
begimane|bagaimana
pake|pakai
pakek|pakai
make|memakai
pengen|ingin
pengin|ingin
pingin|ingin
pinginnya|inginnya
pengennya|inginnya
kepingin|ingin
kepengen|ingin
ngga|tidak
ngg|tidak
engga|tidak
ngak|tidak
gada|tidak ada
gakada|tidak ada
gaada|tidak ada
gakbisa|tidak bisa
gabisa|tidak bisa
gausah|tidak usah
gakusah|tidak usah
gajelas|tidak jelas
gakjelas|tidak jelas
gatau|tidak tahu
gaktau|tidak tahu
gapeduli|tidak peduli
gamau|tidak mau
gakmau|tidak mau
nggatau|tidak tahu
gakboleh|tidak boleh
gaboleh|tidak boleh
gapunya|tidak punya
gakpunya|tidak punya
gamasuk|tidak masuk
gakmasuk|tidak masuk
tp|tetapi
tapi|tetapi
tpi|tetapi
tetep|tetap
sampe|sampai
ampe|sampai
ampe2|sampai-sampai
sampek|sampai
mending|lebih baik
mendingan|lebih baik
semalem|semalam
kemaren|kemarin
kmaren|kemarin
nyokap|ibu
bokap|ayah
dikit|sedikit
dikit2|sedikit-sedikit
dikiiit|sedikit
sedikiiit|sedikit
nggausah|tidak usah
nggakusah|tidak usah
nggakbisa|tidak bisa
nggabisa|tidak bisa
gaenak|tidak enak
gakenak|tidak enak
gaterima|tidak terima
gakpercaya|tidak percaya
gapercaya|tidak percaya
nggaada|tidak ada
nggakada|tidak ada
gapernah|tidak pernah
gakpernah|tidak pernah
ngamuk|mengamuk
ngutang|berutang
ngutangin|mengutangi
ngutanginnya|mengutanginya
hutang|utang
hutangnya|utangnya
mikir|berpikir
mikirin|memikirkan
dipikirin|dipikirkan
ngeliat|melihat
ngelihat|melihat
ngelakuin|melakukan
ngeliatin|melihat
ngelihatin|melihat
ngelakuinnya|melakukannya
ngeles|mengelak
ngibul|berbohong
nyuruh|menyuruh
nyalahin|menyalahkan
ngabisin|menghabiskan
ngabisinnya|menghabiskannya
ngabis|menghabiskan
ngabis2in|menghabis-habiskan
ngambil|mengambil
diambilin|diambilkan
ngasalin|mengerjakan asal-asalan
disuruh2|disuruh-suruh
gapapa|tidak apa-apa
gpp|tidak apa-apa
gakpapa|tidak apa-apa
gppp|tidak apa-apa
gpppp|tidak apa-apa
nggakpapa|tidak apa-apa
gapapalah|tidak apa-apalah
nggpp|tidak apa-apa
udah|sudah
udh|sudah
uda|sudah
udah2|sudah-sudah
udah2lah|sudah-sudahlah
udahlah|sudahlah
udahan|selesai
kayak|seperti
kyk|seperti
kyak|seperti
ky|seperti
kyaknya|sepertinya
kayaknya|sepertinya
kayanya|sepertinya
kyknya|sepertinya
kyaknya|sepertinya
karna|karena
karenaaan|karena
krna|karena
karna|karena
krn|karena
org|orang
orng|orang
orng2|orang-orang
orang2|orang-orang
org2|orang-orang
orgnya|orangnya
anak2|anak-anak
anak2nya|anak-anaknya
anak2ku|anak-anakku
anak2mu|anak-anakmu
anak-anakny|anak-anaknya
mrk|mereka
mrka|mereka
mrk2|mereka
masi|masih
msih|masih
msh|masih
skrg|sekarang
skrang|sekarang
skrng|sekarang
skrg2|sekarang-sekarang
liat|lihat
liatin|lihat
liatnya|lihatnya
keliatan|kelihatan
ngeliatnya|melihatnya
diliat|dilihat
diliatin|dilihat
diliatnya|dilihatnya
liat2|lihat-lihat
nyari|mencari
nyarinya|mencarinya
dicariin|dicarikan
kerjaan|pekerjaan
kerjaannya|pekerjaannya
kerjain|kerjakan
dikerjain|dikerjakan
kerjanya|kerjanya
ngerjain|mengerjakan
ngebantu|membantu
ngebuang|membuang
ngebunuh|membunuh
ngebayar|membayar
ngerusak|merusak
ngerasa|merasa
ngerasaain|merasakan
nyebar|menyebar
nyebarin|menyebarkan
nyebarnya|menyebarnya
nyampe|sampai
nyampein|menyampaikan
nyelesaiin|menyelesaikan
nyelesein|menyelesaikan
selese|selesai
selesei|selesai
ngumpulin|mengumpulkan
dikumpulin|dikumpulkan
ngikut|mengikut
ngikutin|mengikuti
ikutan|ikut
ngikutinnya|mengikutinya
ngerasain|merasakan
ngerjainnya|mengerjakannya
dibiarin|dibiarkan
dikasih|diberi
ngasih|memberi
dikasihin|diberikan
ngasihin|memberikan
ngasih2|memberi-beri
ngasih2nya|memberi-berinya
ngabarin|mengabari
nganter|mengantar
nganterin|mengantarkan
dianter|diantar
dianterin|diantarkan
ngatur|mengatur
ngaturnya|mengaturnya
ngerti|mengerti
ngertiin|mengerti
dimengertiin|dimengerti
denger|dengar
dengerin|dengarkan
ngedenger|mendengar
ngedengerin|mendengarkan
ngedengerinnya|mendengarkannya
dengerannya|dengarannya
didenger|didengar
didengerin|didengarkan
ngobrol|mengobrol
ngobrolin|membicarakan
ngobrolnya|mengobrolnya
ngomongin|membicarakan
diomongin|dibicarakan
ngomongnya|berbicaranya
ngomonginny|membicarakannya
mbaknya|mbaknya
masukin|masukkan
dimasukin|dimasukkan
ngomporin|memprovokasi
nyinyirin|mencibir
ngajarin|mengajari
diajarin|diajari
ngajarinya|mengajarinya
ngajarnya|mengajarnya
ngajar|mengajar
belom|belum
blom|belum
blum|belum
blm|belum
belon|belum
bln|bulan
bulan2|bulan-bulan
thn|tahun
taun|tahun
taonnya|tahunnya
taun2|tahun-tahun
taon|tahun
tanggungjawab|tanggung jawab
bertanggungjawab|bertanggung jawab
bertanggungjawablah|bertanggung jawablah
tanggungjawabnya|tanggung jawabnya
pertanggungjawaban|pertanggungjawaban
kerjasama|kerja sama
bekerjasama|bekerja sama
terimakasih|terima kasih
trimakasih|terima kasih
makasih|terima kasih
makasi|terima kasih
makasii|terima kasih
makasiii|terima kasih
makasihh|terima kasih
trimks|terima kasih
mksh|terima kasih
makasiiih|terima kasih
makasihhh|terima kasih
fikir|pikir
berfikir|berpikir
berfikirnya|berpikirnya
pemikiran|pemikiran
fikirannya|pikirannya
difikir|dipikir
difikirin|dipikirkan
difikirkan|dipikirkan
fikirkan|pikirkan
fikiran|pikiran
resiko|risiko
resikonya|risikonya
beresiko|berisiko
aktifitas|aktivitas
efektifitas|efektivitas
produktifitas|produktivitas
kreatifitas|kreativitas
kwalitas|kualitas
kwalitasnya|kualitasnya
kwantitas|kuantitas
praktek|praktik
prakteknya|praktiknya
ijin|izin
ijinnya|izinnya
perijinan|perizinan
antri|antre
antrian|antrean
ngantri|mengantre
ngantre|mengantre
sekedar|sekadar
sekedarnya|sekadarnya
negri|negeri
negrinya|negerinya
negara2|negara-negara
negri2|negeri-negeri
propinsi|provinsi
propinsinya|provinsinya
standart|standar
standartnya|standarnya
standarisasi|standardisasi
higienis|higienis
higenis|higienis
higenitas|higienitas
hygenis|higienis
nutrition|nutrisi
beneran|sungguh
ntar|nanti
ko|kok
koq|kok
emng|memang
kirain|mengira
keknya|sepertinya
masing2|masing-masing
blg|bilang
yh|ya
cobain|coba
bkin|membuat
nda|tidak
ngakak|tertawa terbahak-bahak
tambahin|tambahkan
urusin|urusi
neh|nih
ngarep|berharap
emak2|ibu-ibu
gni|begini
nich|nih
adek2|adik-adik
bales|balas
nawarin|menawarkan
nyadar|menyadari
ajh|saja
bgni|begini
gabakal|tidak akan
lohh|loh
nihh|nih
sekali2|sekali-sekali
cewe|perempuan
lakuin|lakukan
ngoceh|mengoceh
nie|nih
bagiin|bagikan
omongin|bicarakan
ajarin|ajarkan
beliin|belikan
gituu|begitu
kmn|ke mana
knpa|kenapa
ngaca|berkaca
ngambek|merajuk
ntr|nanti
rame2|ramai-ramai
paksain|paksakan
dmn|di mana
jagain|jaga
keluarin|keluarkan
kog|kok
maafin|maafkan
ngmng|berbicara
yaah|ya
yach|ya
bntr|sebentar
duhh|duh
duhhh|duh
ikutin|ikuti
ingetin|ingatkan
lohhh|loh
lupain|lupakan
rasain|rasakan
tauu|tahu
cuan|keuntungan
plis|tolong
ok|oke
medsos|media sosial
sosmed|media sosial
apasih|apa sih
ngaco|mengacau
taunya|tahunya
kedepannya|ke depannya
ngotot|bersikeras
postingan|unggahan
dibilangin|diberi tahu
ajalah|sajalah
yaelah|ya ampun
sulteng|sulawesi tengah
fyi|sebagai informasi
ultah|ulang tahun
bete|kesal
ceo|direktur utama
malu2in|memalukan
yakan|ya kan
drmn|dari mana
mimin|administrator
nipu|menipu
ojol|ojek daring
ngrasain|merasakan
ketawain|menertawakan
kmna|ke mana
micin|mononatrium glutamat
bersihin|bersihkan
minjem|meminjam
ngemil|mengemil
ngimpi|bermimpi
nyicil|mencicil
nyolong|mencuri
sotoy|sok tahu
copas|salin tempel
cepetan|lebih cepat
diklat|pendidikan dan pelatihan
diupload|diunggah
emot|emotikon
emyu|manchester united
elo2|kamu-kamu
gtu2|begitu-begitu
hape|telepon seluler
kemanapun|ke mana pun
kyanya|sepertinya
mesen|memesan
miara|memelihara
nafass|napas
ngakakkk|tertawa terbahak-bahak
ngambekan|mudah merajuk
ngapa2in|melakukan apa-apa
ngetweet|menulis cuitan
ngomel|mengomel
nugas|mengerjakan tugas
nuhun|terima kasih
nyebrang|menyeberang
nyerocos|mencerocos
omdo|omong doang
peduliin|pedulikan
sewain|sewakan
tauuuu|tahu
tuhhh|itu
yaoloh|ya allah
yekan|ya kan
sedulur|saudara
berantem|bertengkar
bullshit|omong kosong
koyo|seperti
nggo|memakai
ngadem|menyejukkan diri
ngiri|iri
nyolot|membantah dengan kasar
nganu|anu
meneh|lagi
mknn|makanan
pisan|sangat
arep|akan
mikirnya|berpikirnya
dimana2|di mana-mana
dihh|idih
hehee|hahaha
samperin|datangi
baper|terbawa perasaan
baperan|mudah terbawa perasaan
gedeg|kesal
bacod|bacot
bct|bacot
"""

EXCLUDED_TARGETS = set("""
anjing anjir anjay mengentot entot asu koyok silahkan tertara
menampak tensorflow vestin meant meanu emote
""".split())

ELONGATION_BASES = """
tidak iya ya bukan belum jangan sangat sekali benar salah sudah
baik bagus buruk busuk basi mahal murah gratis rakyat sekolah
anak makan makanan keracunan racun program pemerintah presiden
susah senang sedih sakit sehat lapar kenyang malu malu-malu
tolol bodoh goblok bangsat aneh kacau jijik menjijikkan
saja semoga selamat terima kasih maaf ampun allah amin
ini itu juga apa kenapa bagaimana begini begitu
kamu kalian kita saya aku mereka kami
pantas jelas betul tidak mungkin tahu mau bisa boleh
makin lebih banyak sedikit gila parah susah mudah
kasihan aduh duh wah kok sih dong lah deh nih loh
halo hai heh oh ah ih astaga astagfirullah alhamdulillah
pintar pintar-pintar hebat keren mantap senang lelah
uang uangnya dana anggaran pajak korupsi koruptor
nyata betapa lucu semangat setuju rusak kacau
"""


def elongations(frequencies, records):
    known = {r["slang"] for r in records}
    bases = {word: canonical(word) for word in ELONGATION_BASES.split()}
    bases.update({r["slang"]: r["kata_baku"] for r in records if r["sumber"] == ["review_local"]})
    collapsed = collections.defaultdict(set)
    for word, value in bases.items():
        collapsed[re.sub(r"(.)\1+", r"\1", word)].add(value)
    extra = []
    for word in frequencies:
        if word in known or word in PROTECTED or len(word) < 4:
            continue
        if not re.fullmatch(r"[a-z]+", word) or not re.search(r"(.)\1", word):
            continue
        reduced = re.sub(r"(.)\1+", r"\1", word)
        options = collapsed.get(reduced, set())
        if len(options) == 1:
            value = next(iter(options))
            if word != value:
                extra.append({"slang": word, "kata_baku": value, "frekuensi": frequencies[word], "sumber": ["elongation_local"]})
    return extra


def manual_mapping():
    pairs = {}
    for line in MANUAL_TEXT.strip().splitlines():
        key, value = line.split("|", 1)
        if key in pairs and pairs[key] != value:
            raise ValueError(f"Conflicting manual mapping: {key}")
        pairs[key] = value
    return pairs


def canonical(value):
    value = " ".join(value.lower().split())
    for _ in range(5):
        updated = " ".join(CANONICAL.get(t, t) for t in value.split())
        if updated == value:
            return value
        value = updated
    raise ValueError(f"Canonicalization cycle: {value}")


def fetch_sources():
    result = {}
    for name, url in SOURCES.items():
        path = HERE / (name + (".tsv" if name == "indocollex" else ".csv"))
        if not path.exists():
            with urllib.request.urlopen(url, timeout=30) as response:
                path.write_bytes(response.read())
        result[name] = path
    license_path = HERE / "IndoCollex_LICENSE.txt"
    if not license_path.exists():
        url = "https://raw.githubusercontent.com/haryoa/indo-collex/main/LICENSE"
        with urllib.request.urlopen(url, timeout=30) as response:
            license_path.write_bytes(response.read())
    return result


def corpus():
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, strict=True))
    frequencies = collections.Counter()
    for row in rows:
        frequencies.update(TOKEN.findall(row["Content_Cleansing"]))
    return rows, frequencies


def candidates(frequencies, paths):
    choices = collections.defaultdict(lambda: collections.defaultdict(set))
    for name, path in paths.items():
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t" if name == "indocollex" else ","):
                key = row["informal" if name == "indocollex" else "slang"].strip().lower()
                value = canonical(row["formal"])
                if key in frequencies and key != value and value:
                    choices[key][value].add(name)
    for key, value in manual_mapping().items():
        if key in frequencies and key != value:
            choices[key] = {canonical(value): {"review_local"}}
    records = []
    conflicts = []
    for key, options in choices.items():
        if key in PROTECTED or not TOKEN.fullmatch(key):
            continue
        if len(options) != 1:
            conflicts.append({"slang": key, "options": sorted(options), "frekuensi": frequencies[key]})
            continue
        value, sources = next(iter(options.items()))
        if value == key or value in EXCLUDED_TARGETS or not re.fullmatch(r"[a-z][a-z '-]*", value):
            continue
        records.append({"slang": key, "kata_baku": value, "frekuensi": frequencies[key], "sumber": sorted(sources)})
    records.extend(elongations(frequencies, records))
    records.sort(key=lambda row: (-row["frekuensi"], row["slang"]))
    return records, sorted(conflicts, key=lambda row: -row["frekuensi"])


def fingerprint():
    paths = [SOURCE, OUTPUT / "MBG_Dataset_DirectReplies_20260907_0825.csv"]
    paths.extend(sorted(OUTPUT.glob("checkpoint*.json")))
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def verify_csv(path, frequencies, expected):
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        assert reader.fieldnames == FIELDS
        rows = list(reader)
    assert len(rows) == expected
    assert len({r["slang"] for r in rows}) == expected
    for row in rows:
        assert set(row) == set(FIELDS)
        assert all(row.values())
        assert row["slang"] != row["kata_baku"]
        assert row["slang"] == row["slang"].lower()
        assert row["kata_baku"] == row["kata_baku"].lower()
        assert row["slang"] not in PROTECTED
        assert int(row["frekuensi"]) == frequencies[row["slang"]] > 0
    return rows


def select_mapping(records, count=2000):
    # At equal frequency, prefer lexical entries over one-off letter repetitions.
    ranked = sorted(records, key=lambda row: (
        -row["frekuensi"],
        row["sumber"] == ["elongation_local"],
        row["sumber"] != ["review_local"],
        row["slang"],
    ))
    return sorted(ranked[:count], key=lambda row: (-row["frekuensi"], row["slang"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    before = fingerprint()
    paths = fetch_sources()
    rows, frequencies = corpus()
    records, conflicts = candidates(frequencies, paths)
    (HERE / "candidates.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    (HERE / "conflicts.json").write_text(json.dumps(conflicts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"source_rows": len(rows), "vocabulary": len(frequencies), "candidates": len(records), "conflicts": len(conflicts)}))
    if args.build:
        if len(records) < 2000:
            raise ValueError("Fewer than 2000 supported mappings; no filler will be generated")
        selected = select_mapping(records)
        with DESTINATION.open("x", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(selected)
        verified = verify_csv(DESTINATION, frequencies, 2000)
        assert before == fingerprint(), "Source CSV or checkpoint changed"
        selected_keys = {r["slang"] for r in selected}
        report = {
            "source_file": SOURCE.name, "source_rows": len(rows),
            "source_unique_tweet_ids": len({r["Tweet_ID"] for r in rows}),
            "output_file": DESTINATION.name, "mapping_rows": len(verified),
            "columns": FIELDS, "all_slang_observed_in_source": True,
            "frequency_definition": "Occurrences in all 20000 rows, including existing duplicate Tweet_ID rows",
            "source_and_checkpoints_unchanged": True, "input_sha256": before,
            "output_sha256": hashlib.sha256(DESTINATION.read_bytes()).hexdigest(),
            "sources": {name: {"url": SOURCES[name], "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for name, p in paths.items()},
            "mapping_provenance": selected,
            "selection": "Frequency descending; ties prefer local review, then lexicons, then local elongation. Final display: frequency descending, slang alphabetical.",
            "provenance_counts": dict(collections.Counter("+".join(r["sumber"]) for r in selected)),
            "covered_token_occurrences": sum(r["frekuensi"] for r in selected),
            "covered_rows": sum(any(t in selected_keys for t in TOKEN.findall(row["Content_Cleansing"])) for row in rows),
        }
        (HERE / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"output": str(DESTINATION), "rows": len(verified), "verified": True}))


if __name__ == "__main__":
    main()
