import re
import string
import json
import random
import copy

with open('config.json') as file:
    CONFIG = json.load(file)

with open('samples.json') as file:
    SAMPLES = json.load(file)

with open('context.json') as file:
    CONTEXT = json.load(file)

with open('contractions.json') as file:
    CONTRACTIONS = json.load(file)

WEIGHT_PHRASE_EXACT = CONFIG["weights"]["phrase_exact"]
WEIGHT_PHRASE_PARTIAL = CONFIG["weights"]["phrase_partial"]
WEIGHT_WORD_EXACT = CONFIG["weights"]["word_exact"]
WEIGHT_WORD_PARTIAL = CONFIG["weights"]["word_partial"]
WEIGHT_CHARACTER_EXACT = CONFIG["weights"]["character_exact"]
WEIGHT_CHARACTER_PARTIAL = CONFIG["weights"]["character_partial"]
MINIMUM_CONFIDENCE = CONFIG["minimum_confidence"]
SPECIAL_KEYS = CONFIG["special_keys"]
COULD_NOT_UNDERSTAND_RESPONSES = CONFIG["could_not_understand"]

SPECIAL_KEY_SAFE_PUNCTUATION = "!@#$^&*()+={}|\\:;\"'<>,.?/~`"
LIST_SEPARATORS = ["and", "or"]

def levenshtein_distance(str1, str2):
    # Get the lengths of the input strings
    m = len(str1)
    n = len(str2)
 
    # Initialize two rows for dynamic programming
    prev_row = [j for j in range(n + 1)]
    curr_row = [0] * (n + 1)
 
    # Dynamic programming to fill the matrix
    for i in range(1, m + 1):
        # Initialize the first element of the current row
        curr_row[0] = i
 
        for j in range(1, n + 1):
            if str1[i - 1] == str2[j - 1]:
                # Characters match, no operation needed
                curr_row[j] = prev_row[j - 1]
            else:
                # Choose the minimum cost operation
                curr_row[j] = 1 + min(
                    curr_row[j - 1],  # Insert
                    prev_row[j],      # Remove
                    prev_row[j - 1]    # Replace
                )
 
        # Update the previous row with the current row
        prev_row = curr_row.copy()
 
    # The final element in the last row contains the Levenshtein distance
    return curr_row[n]

def removePunctuation(text: str, punctuation: str = string.punctuation) -> str:
    translation_table = str.maketrans('', '', punctuation)
    return text.translate(translation_table)

def normalize(text: str) -> str:
    text = removePunctuation(text.casefold())

    for contraction, expansion in CONTRACTIONS.items():
        text = re.sub(fr'\b{contraction.casefold()}\b', expansion.casefold(), text)

    return re.sub(r'\s+', ' ', text).strip()

def parseSpecialKey(key: str) -> dict[str, str]:
    key = removePunctuation(key, SPECIAL_KEY_SAFE_PUNCTUATION)

    if key[0] != '%' or key[-1] != '%': return None

    actual_key = key[1:-1]
    type = ""
    prefix = ""

    for index, value in SPECIAL_KEYS.items():        
        if isinstance(value, dict):
            for prefix_index, prefix in value["prefixes"].items():
                match = re.search(fr"{prefix}{value["key"]}", actual_key)

                if match is None: continue

                type = index
                prefix = prefix_index
                actual_key = actual_key.replace(match.group(0), "")
                break

            if len(type) > 0: break
        elif re.search(fr"{key}", actual_key) is not None:
            type = index
            actual_key = re.sub(key, "", actual_key)
            break

    return { "key": actual_key, "raw": key, "type": type, "prefix": prefix }

# Replaces all the special tokens in the response with the values from the context
def parseResponse(response):
    for key in response.split():
        key = parseSpecialKey(key)

        if key is None: continue

        value = CONTEXT.get(key["key"], None)

        if value is None:
            value = "nothing"
        elif key["type"] == "list":
            if key["prefix"] == "get":
                if len(value) > 1:
                    value = ", ".join(value[:-1]) + " and " + value[-1]
                elif len(value) == 1:
                    value = value[0]
            elif key["prefix"] == "index":
                index_match = re.search(r'(-?\d+)', key["raw"])

                if index_match:
                    index = int(index_match.group(1))

                    if index > len(value) or index < -len(value): index = 0

                    value = value[index]
                else:
                    value = "[No index specified]"

        response = response.replace(key["raw"], value)

    return response

def processUserMessage(message: str) -> str:
    message_unnormalized = message
    message_unnormalized_words = message_unnormalized.split()
    message = normalize(message)
    message_words = message.split()

    best_sample_confidence = 0
    potential_response_indexes = []
    potential_contexts = {}

    for sample_index, sample in enumerate(SAMPLES):
        sample_input_no_punctuation = removePunctuation(sample["input"], SPECIAL_KEY_SAFE_PUNCTUATION)
        sample_input = normalize(re.sub(r'%[-_a-zA-Z]+%', '', sample["input"]))
        sample_words_raw = sample_input.split()
        sample_words = []
        sample_characters = []

        for character in sample_input:
            if character in sample_characters: continue

            sample_characters.append(character)

        for word in sample_input.split():
            if word in sample_words: continue

            sample_words.append(word)

        sample_input_score = 0
        sample_input_max_score = (
            len(sample_words_raw) * WEIGHT_WORD_EXACT +
            len(sample_words) * WEIGHT_WORD_PARTIAL +
            len(sample_input) * WEIGHT_CHARACTER_EXACT +
            len(sample_characters) * WEIGHT_CHARACTER_PARTIAL
        )

        if message == sample_input:
            sample_input_score = sample_input_max_score
        else:
            # Match each character
            for index, character in enumerate(sample_input):
                if index >= len(message): break
                if character != message[index]: continue
                
                sample_input_score += WEIGHT_CHARACTER_EXACT

            for character in sample_characters:
                if character not in message: continue
                
                sample_input_score += WEIGHT_CHARACTER_PARTIAL

            # Match each word
            for index, word in enumerate(sample_words_raw):
                if index >= len(message_words): break
                if word != message_words[index]: continue
                
                sample_input_score += WEIGHT_WORD_EXACT

            for word in sample_words:
                if word not in message_words: continue
                
                sample_input_score += WEIGHT_WORD_PARTIAL

            # Match phrases
            current_phrase = ""
            current_phrase_indexes = []

            for index, word in enumerate(message_words):
                potential_phrase = f"{current_phrase} {word}".strip()

                # If the phrase is less than one word, skip it
                if len(potential_phrase) <= 1: continue

                phrase_score = WEIGHT_PHRASE_EXACT
                
                if potential_phrase in sample_input:
                    phrase_score += WEIGHT_PHRASE_PARTIAL

                # Check all the words in the phrase to see if they are the same in the exact same spot in the sample input. If they arent remove the phrase exact score
                for index, word in enumerate(current_phrase_indexes):
                    if word != sample_words[index]:
                        phrase_score -= WEIGHT_PHRASE_EXACT
                        break
                
                if phrase_score > 0:
                    current_phrase = potential_phrase
                    current_phrase_indexes.append(index)
                else:
                    # If the phrase didnt match reset it
                    current_phrase = ""
                    current_phrase_indexes = []

        special_tokens = []

        # Find all the special tokens are in the sample
        for index, token in enumerate(sample_input_no_punctuation.split()):
            key = parseSpecialKey(token)

            if key is None: continue

            special_tokens.append(key)

        # Only create a context if there are special tokens
        if len(special_tokens) > 0:
            context = copy.deepcopy(CONTEXT)

            # Loop through all special tokens and check if they are in the input
            for key in special_tokens:
                value = []
                starting_index = 0

                for index, word in enumerate(message_unnormalized_words):
                    word = normalize(word)

                    if index >= len(sample_words_raw):
                        ratio = 0
                    else:
                        ratio = levenshtein_distance(word, sample_words_raw[index]) / max(len(word), len(sample_words_raw[index]))

                    if word in sample_input or ratio > 0.5: continue

                    starting_index = index
                    break

                for index, word in enumerate(message_unnormalized_words):
                    if index < starting_index: continue

                    # The unnormalized word is used for the context, but the normalized word is used for the levenshtein distance and comparison to the sample input
                    word_unnormalized = word
                    word = normalize(word)

                    if index >= len(sample_words_raw):
                        ratio = 0
                    else:
                        ratio = levenshtein_distance(word, sample_words_raw[index]) / max(len(word), len(sample_words_raw[index]))

                    if index + 1 >= len(sample_words_raw) or index + 1 >= len(message_words):
                        next_word = None
                        next_word_ratio = 0
                    else:
                        next_word = normalize(message_words[index + 1]) if index + 1 < len(message_words) else None
                        next_word_ratio = levenshtein_distance(next_word, sample_words_raw[index + 1]) / max(len(next_word), len(sample_words_raw[index + 1]))
                    
                    # If the word is in the sample input and the next word is in the sample input or the ratio is greater than 0.5, skip it
                    if (word in sample_input or ratio > 0.5) and (next_word is None or next_word in sample_input or next_word_ratio > 0.5): continue

                    value.append(word_unnormalized)

                if len(value) == 0: continue

                value = [removePunctuation(word, "!@#$^&*()+={}|\\:;\"<>.?/~`") for word in value]

                if key["type"] == "list":
                    if key["key"] not in context:
                        context[key["key"]] = []

                    value_corrected = []
                    current_string = ""

                    # Parse the list into separate words. Separate words are separated by commas, periods, or common list separators like "and" or "or".
                    for index, word in enumerate(value):
                        if word.endswith(",") or word.endswith(".") or word in LIST_SEPARATORS or index == len(value) - 1:
                            if word not in LIST_SEPARATORS: current_string += removePunctuation(word)
                            if len(current_string) > 0: value_corrected.append(current_string.strip())

                            current_string = ""
                        else:
                            current_string += f"{word.strip()} "

                    if key["prefix"] == "add":
                        for word in value_corrected:
                            if word in context[key["key"]]:
                                context[key["key"]].remove(word)

                            context[key["key"]].append(removePunctuation(word))
                    elif key["prefix"] == "remove":
                        for word in value_corrected:
                            if word in context[key["key"]]:
                                context[key["key"]].remove(word)
                    elif key["prefix"] == "set":
                        context[key["key"]] = value_corrected
                    elif key["prefix"] == "clear":
                        context[key["key"]] = []
                elif key["type"] == "string":
                    value = " ".join(value)

                    if key["prefix"] == "set":
                        context[key["key"]] = value
                    elif key["prefix"] == "get":
                        sample_input_max_score += WEIGHT_WORD_EXACT

                        if value == context[key["key"]]: sample_input_score += WEIGHT_WORD_EXACT

            potential_contexts[sample_index] = context

        sample_confidence = sample_input_score / sample_input_max_score

        # Add it to the list of potential contexts if a good match
        if sample_confidence < MINIMUM_CONFIDENCE:
            continue
        elif sample_confidence > best_sample_confidence:
            best_sample_confidence = sample_confidence
            potential_response_indexes = [sample_index]
        elif sample_confidence > best_sample_confidence:
            potential_response_indexes.append(sample_index)

        # If the confidence is 1.0, we can break early as we have a perfect match
        if best_sample_confidence >= 1.0: break

    # If there are no potential responses, return a random response from the "could not understand" list
    if len(potential_response_indexes) == 0: return parseResponse(random.choice(COULD_NOT_UNDERSTAND_RESPONSES))
    
    # Return a random response from the potential responses if there are multiple
    best_response_index = None

    if len(potential_response_indexes) == 1:
        best_response_index = potential_response_indexes[0]
    elif len(potential_response_indexes) > 1:
        best_response_index = random.choice(potential_response_indexes)

    # Update the context with the best response's context, if it exists
    if best_response_index in potential_contexts:
        for key, value in potential_contexts[best_response_index].items():
            CONTEXT[key] = value

        with open('context.json', 'w') as file:
            json.dump(CONTEXT, file, indent=4)

    return parseResponse(SAMPLES[best_response_index]["response"])


while True:
    userMessage = input(f'{CONTEXT.get("user_name", "You")}: ')
    response = processUserMessage(userMessage)
    print(f"{CONTEXT.get("bot_name", "Bot")}: {response}")