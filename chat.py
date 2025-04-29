import json
import random
import re

LIST_KEY = "LIST"
RESPONSE_LIST_KEY = "RESPONSELIST"
MINIMUM_SCORE = 0.3
COULD_NOT_UNDERSTAND = "Im sorry, I could not understand that. Could you please rephrase?"
EXACT_MATCH_WEIGHT = 2
MATCH_WEIGHT = 1

conversationMeta = {}

with open('data.json') as file:
    sampleConversations = json.load(file)

# Replaces all the special tokens in the response with the values from conversationMeta
def parseResponse(response):
    for key in response.split():
        # This prevents punctuation from being included in the key
        key = re.sub(r'[^a-zA-Z0-9%]+', "", key)
        
        if key[0] != '%' or key[-1] != '%': continue

        actualKey = key[1:-1].replace(RESPONSE_LIST_KEY, "").replace(LIST_KEY, "")
        value = conversationMeta.get(actualKey, None)

        if value is None: continue

        if RESPONSE_LIST_KEY in key:
            # The first index is the most recent response, so we only use that one
            value = value[-1]
        elif LIST_KEY in key:
            if len(value) > 1:
                value = ", ".join(value[:-1]) + " and " + value[-1]
            elif len(value) == 1:
                value = value[0]

        response = response.replace(key, value)

    return response

def determineResponse(userInput):
    userInput = userInput.lower()
    inputTokens = list(userInput)
    tempConversationMeta = {}

    bestScore = 0
    bestResponses = []

    for responseIndex, potentialResponse in enumerate(sampleConversations):
        sampleInput = potentialResponse['input'].lower().replace(r'%[a-zA-Z]+%', '')
        inputScore = 0

        # If its an exact match, we can skip the rest of the checks
        if userInput == sampleInput:
            bestScore = inputScore
        else:
            # If not an exact match then match by words and characters. +2 if its an exact match and +1 for it being in the sampleInput
            for index, character in enumerate(inputTokens):
                if index >= len(sampleInput): break

                if character == sampleInput[index]:
                    inputScore += 1 * EXACT_MATCH_WEIGHT

                if character in sampleInput:
                    inputScore += 1 * MATCH_WEIGHT

            for index, word in enumerate(userInput.split()):
                if index >= len(sampleInput): break

                if word == sampleInput[index]:
                    inputScore += 0.5 * EXACT_MATCH_WEIGHT

                if word in sampleInput:
                    inputScore += 0.5 * MATCH_WEIGHT

        # Filter out responses that do not meet the minimum score threshold
        maxCharacterScore = len(sampleInput) * (EXACT_MATCH_WEIGHT + MATCH_WEIGHT)
        maxWordScore = len(sampleInput.split()) * (0.5 * EXACT_MATCH_WEIGHT + 0.5 * MATCH_WEIGHT)

        if inputScore / (maxCharacterScore + maxWordScore) < MINIMUM_SCORE: continue

        specialTokens = {}

        # Find all the special tokens are in the sample
        for index, token in enumerate(potentialResponse['input'].split()):
            if re.match(r"%[a-zA-Z]+%", token):
                specialTokens[index] = token

        # Only create a new conversationMeta if there are special tokens in the input
        if len(specialTokens) > 0: tempConversationMeta[responseIndex] = conversationMeta.copy()

        # Loop through all special tokens and check if they are in the input
        for specialIndex, specialToken in specialTokens.items():
            key = re.search(r"%[a-zA-Z]+%", specialToken).group(0)[1:-1]
            value = None

            if specialIndex < len(userInput):
                if userInput.split()[specialIndex] not in potentialResponse['input'].lower():
                    value = userInput.split()[specialIndex]
            else:
                # Find any word thats not in the input
                for index, token in enumerate(inputTokens):
                    if token in sampleInput: continue

                    value = token
                    break

                # If no value is found find the word that repeats the most in the input
                if value is None:
                    for index, token in enumerate(inputTokens):
                        if userInput.count(token) > sampleInput.count(token):
                            value = token
                            break

            if value is None: continue

            value = re.sub(r'[^a-zA-Z]+', "", value)
            
            # If its a list then we need to add the item to the list
            if LIST_KEY in key or RESPONSE_LIST_KEY in key:
                actualKey = key.replace(RESPONSE_LIST_KEY, "").replace(LIST_KEY, "")

                if actualKey not in tempConversationMeta[responseIndex]:
                    tempConversationMeta[responseIndex][actualKey] = [value]
                elif value not in tempConversationMeta[responseIndex][actualKey]:
                    tempConversationMeta[responseIndex][actualKey].append(value)
            else:
                tempConversationMeta[responseIndex][key] = value

        if inputScore == bestScore:
            bestResponses.append(responseIndex)
        elif inputScore > bestScore:
            bestScore = inputScore
            bestResponses = [responseIndex]

    if len(bestResponses) == 0: return COULD_NOT_UNDERSTAND
    
    bestResponseIndex = None

    if len(bestResponses) == 1:
        bestResponseIndex = bestResponses[0]
    elif len(bestResponses) > 1:
        bestResponseIndex = random.choice(bestResponses)

    # Update the conversationMeta with the best response's metadata
    if bestResponseIndex in tempConversationMeta:
        for key, value in tempConversationMeta[bestResponseIndex].items():
            conversationMeta[key] = value

    return parseResponse(sampleConversations[bestResponseIndex]["response"])


while True:
    userInput = input(f'{conversationMeta.get("name", "You")}: ')
    print(f'{conversationMeta.get("bot", "Bot")}: {determineResponse(userInput)}')