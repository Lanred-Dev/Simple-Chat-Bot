import re
import string
import json
import random

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

    actualKey = key[1:-1]
    type = ""
    prefix = ""

    for index, value in SPECIAL_KEYS.items():        
        if isinstance(value, dict):
            for prefix_index, prefix in value["prefixes"].items():
                match = re.search(fr"{prefix}{value["key"]}", actualKey)

                if match is None: continue

                type = index
                prefix = prefix_index
                
                # Remove the exact text that was matched, rather than trying to reconstruct the pattern
                matched_text = match.group(0)
                actualKey = actualKey.replace(matched_text, "")
                break

            if len(type) > 0: break
        elif re.search(fr"{key}", actualKey) is not None:
            type = index
            actualKey = re.sub(key, "", actualKey)
            break

    return { "key": actualKey, "raw": key, "type": type, "prefix": prefix }

# Replaces all the special tokens in the response with the values from the context
def parseResponse(response):
    for key in response.split():
        key = parseSpecialKey(key)

        if key is None: continue

        value = CONTEXT.get(key["key"], None)

        if value is None: continue

        if key["type"] == "list":
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
    message = normalize(message)
    message_words = message.split()

    best_sample_confidence = 0
    potential_response_indexes = []
    potential_contexts = {}

    for sample_index, sample in enumerate(SAMPLES):
        sample_input_no_punctuation = removePunctuation(sample["input"], SPECIAL_KEY_SAFE_PUNCTUATION)
        sample_input = normalize(re.sub(r'%[-_a-zA-Z]+%', '', sample["input"]))
        sample_words = sample_input.split()

        sample_input_score = 0
        sample_input_max_score = (
            len(sample_words) * WEIGHT_WORD_EXACT +
            len(sample_words) * WEIGHT_WORD_PARTIAL +
            len(sample_input) * WEIGHT_CHARACTER_EXACT +
            len(sample_input) * WEIGHT_CHARACTER_PARTIAL
        )

        if message == sample_input:
            sample_input_score = sample_input_max_score
        else:
            # Match each character
            for index, character in enumerate(sample_input):
                if index >= len(message): break

                if character == message[index]:
                    sample_input_score += WEIGHT_CHARACTER_EXACT

                if character in message:
                    sample_input_score += WEIGHT_CHARACTER_PARTIAL

            # Match each word
            for index, word in enumerate(sample_words):
                if index >= len(sample_words): break

                if word == sample_words[index]:
                    sample_input_score += WEIGHT_WORD_EXACT

                if word in sample_words:
                    sample_input_score += WEIGHT_WORD_PARTIAL

        special_tokens = {}

        # Find all the special tokens are in the sample
        for index, token in enumerate(sample_input_no_punctuation.split()):
            key = parseSpecialKey(token)

            if key is None: continue

            special_tokens[index] = key

        # Only create a context if there are special tokens
        if len(special_tokens) > 0:
            context = CONTEXT.copy()

            # Loop through all special tokens and check if they are in the input
            for special_index, key in special_tokens.items():
                value = None

                if special_index < len(message_words) and message_words[special_index] not in sample_input:
                    value = message_words[special_index]
                else:
                    # Look for any words not in the sample input, this could be a phrase or a word
                    # 1. First try to find words close to the expected special token position
                    nearby_range = 2  # Look 2 words before and after the expected position
                    candidate_words = []

                    # Try positions near the expected special token position first
                    start_pos = max(0, special_index - nearby_range)
                    end_pos = min(len(message_words), special_index + nearby_range + 1)

                    for index in range(start_pos, end_pos):
                        if index < len(message_words) and message_words[index] not in sample_input:
                            candidate_words.append((message_words[index], abs(index - special_index)))

                    # Then look through all words if we haven't found candidates
                    if not candidate_words:
                        for index, word in enumerate(message_words):
                            if word in sample_input: continue

                            candidate_words.append((word, abs(index - special_index)))
                                
                    # Pick the word closest to the expected position, or the first one if none found
                    if candidate_words:
                        # Sort by distance from expected position
                        candidate_words.sort(key=lambda x: x[1])
                        value = candidate_words[0][0]
                    else:
                        for index, word in enumerate(message_words):
                            if message.count(word) <= sample_input.count(word): continue

                            value = word
                            break

                if value is None or len(value) == 0: continue

                value = re.sub(r'[^a-zA-Z]+', "", value)

                if key["type"] == "list":
                    if key["key"] not in context:
                        context[key["key"]] = []

                    if key["prefix"] == "add":
                        if value in context[key["key"]]:
                            context[key["key"]].remove(value)
                        
                        context[key["key"]].append(value)
                    elif key["prefix"] == "remove":
                        context[key["key"]].remove(value)
                    elif key["prefix"] == "set":
                        context[key["key"]] = value.split(",")
                    elif key["prefix"] == "clear":
                        context[key["key"]] = []
                elif key["type"] == "string":
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
    print(f"{CONTEXT.get("bot_name", "Bot")}: {processUserMessage(userMessage)}")