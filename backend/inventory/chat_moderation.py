import re
from unicodedata import category, normalize

from rest_framework.exceptions import ValidationError


# Match whole forms so ordinary words, names and longer identifiers can still be sent.
BLOCKED_WORDS = frozenset("""
fuck fucks fucker fucking fucked motherfucker motherfucking shit shits shitty bullshit asshole assholes
bitch bitches bastard dick dickhead cunt wanker
хуй хуя хуем хую хуйня хуйни хуйню хуёвый хуевый хуёво хуево нахуй похуй
пизда пиздец пизду пизде пизды пиздой пиздеть пиздёж пиздеж пиздатый
блядь блять бля бляди блядский сука суки суку сукой
ебать ёбать ебаный ёбаный ебаная ёбаная ебанутый заебал заёбал заебала заёбала заебись
мудак мудаки мудила гандон говно говна дерьмо дерьма долбоёб долбаёб долбоеб долбаеб
боқ боқты боқтық боқта боқтай боқбас қотақ қотақты котак котакбас қотақбас
mierda carajo joder gilipollas cabrón cabrones pendejo pendeja puta puto coñazo
merde putain connard connarde connards connasses connasse enfoiré salope enculé
scheiße scheisse arschloch arschlöcher scheißegal hurensohn wichser
cazzo merda stronzo stronza vaffanculo coglione coglioni
porra caralho foda foder fodase buceta arrombado desgraçado
siktir amk amına orospu pezevenk
kurwa kurwy kurewski pierdolić pierdolę spierdalaj skurwysyn
пиздець хріновий курва їбати єбати довбойоб підар підорас дупа
""".split())

TOKEN = re.compile(r"[^\W_]+")
# Symbol substitutions inside Latin words, such as sh!t and b@stard.
MIXED_TOKEN = re.compile(r"(?<![\w@$!])[a-z0-9@$!]+(?![\w@$!])")
SPACED_LETTERS = re.compile(r"(?<!\w)[^\W\d_](?:[.\-_*·~ \t]{1,3}[^\W\d_]){2,}(?!\w)")
MASKED_TERMS = re.compile(
    r"(?<!\w)(?:f(?:\*+ck|\*{2,}k)|s(?:h\*+t|\*{2,}t)|b\*+tch|х\*+й|п\*+здец)(?!\w)"
)
REPEATED = re.compile(r"(.)\1+")
LATIN = re.compile(r"[a-z]")
LETTER_SUBSTITUTIONS = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i",
    "а": "a", "е": "e", "і": "i", "о": "o", "р": "p", "с": "c", "х": "x", "к": "k",
})
PROFANITY_MESSAGE = "Please remove profanity before sending the message."


def word_forms(word):
    yield word
    yield REPEATED.sub(r"\1", word)
    if LATIN.search(word):
        converted = word.translate(LETTER_SUBSTITUTIONS)
        yield converted
        yield REPEATED.sub(r"\1", converted)


WORD_FORMS = frozenset(form for word in BLOCKED_WORDS for form in word_forms(word))


def blocked(word):
    return len(word) >= 3 and any(form in WORD_FORMS for form in word_forms(word))


def spaced_profanity(text):
    for match in SPACED_LETTERS.finditer(text):
        letters = TOKEN.findall(match[0])
        for start in range(len(letters) - 2):
            for end in range(start + 3, min(len(letters), start + 18) + 1):
                if blocked("".join(letters[start:end])):
                    return True
    return False


def check_message(body):
    visible = "".join(char for char in body if category(char) != "Cf")
    text = normalize("NFKC", visible).casefold().replace("i\u0307", "i")
    if (
        MASKED_TERMS.search(text)
        or any(blocked(word) for word in TOKEN.findall(text))
        or any(blocked(word.strip("!")) for word in MIXED_TOKEN.findall(text))
        or spaced_profanity(text)
    ):
        raise ValidationError({"detail": PROFANITY_MESSAGE}, code="profanity")
