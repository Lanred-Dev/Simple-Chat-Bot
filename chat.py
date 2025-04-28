import json
import random
import re

LIST_KEY = "LIST"

conversationMeta = {}

with open('data.json') as file:
    data = json.load(file)

def parseResponse(response):
    for key, value in conversationMeta.items():
        if str(key) in response:
            if LIST_KEY in key:
                if len(value) > 1:
                    value = ", ".join(value[:-1]) + " and " + value[-1]
                elif len(value) == 1:
                    value = value[0]
            
            response = response.replace(f'%{key}%', value)

    return response

def determineResponse(input):
    tokens = input.lower().split()
    bestScore = 0
    bestResponse = None
    responses = []
    tempConversationMeta = {}

    for responseIndex, sampleResponse in enumerate(data):
        sampleInput = sampleResponse['input'].lower().replace(r'%[a-zA-Z]+%', '')
        score = 0
        sampleTokens = sampleInput.split()

        # First match by tokens. This matches every character, +2 if its an exact match and +1 for it being in the input
        for index, token in enumerate(tokens):
            if index >= len(sampleTokens):
                break

            if token == sampleTokens[index]:
                score += 1

            if token in sampleInput:
                score += 1

        specialPositions = {}

        # Find all the special tokens are in the sample
        for index, token in enumerate(sampleResponse['input'].split()):
            if re.match(r"%[a-zA-Z]+%", token):
                specialPositions[index] = token

        # Only create a new conversationMeta if there are special tokens in the input
        if len(specialPositions) > 0: tempConversationMeta[responseIndex] = conversationMeta.copy()

        # Loop through all special tokens and check if they are in the input
        for specialIndex, specialToken in specialPositions.items():
            key = re.search(r"%[a-zA-Z]+%", specialToken).group(0)[1:-1]
            input_tokens = input.lower().split(" ")
            special = None

            # Check the position first (making sure the index is valid)
            if specialIndex < len(input_tokens):  # Changed <= to < to avoid index out of range
                if input_tokens[specialIndex] not in sampleResponse['input'].lower():
                    special = input_tokens[specialIndex]
            else:
                # Then check to find any word thats not in the input
                for index, token in enumerate(input_tokens):
                    if token in sampleInput: continue

                    special = token
                    break

            if special is None: continue

            special = re.sub(r'[^a-zA-Z]+', "", special)
            
            # If its a list then we need to add the item to the list
            if LIST_KEY in key:
                if key not in tempConversationMeta[responseIndex]:
                    tempConversationMeta[responseIndex][key] = [special]
                else:
                    tempConversationMeta[responseIndex][key].append(special)
            else:
                tempConversationMeta[responseIndex][key] = special
                
        score = score / len(sampleInput)

        if score >= bestScore:
            bestScore = score
            bestResponse = responseIndex
            responses = [responseIndex]

        if score == bestScore:
            responses.append(responseIndex)

    if len(responses) > 1:
        bestResponse = random.choice(responses)

    if bestResponse in tempConversationMeta:
        for key, value in tempConversationMeta[bestResponse].items():
            conversationMeta[key] = value

    return parseResponse(data[bestResponse]["response"])


while True:
    userInput = input('You: ')
    response = determineResponse(userInput)
    print(conversationMeta.get("bot", "Bot") + ':', response)