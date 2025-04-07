# import the array from data.json
import json
import random

conversationMeta = {}

with open('data.json') as file:
    data = json.load(file)

def determineResponse(input):
    tokens = input.lower().split()
    bestScore = 0
    bestResponse = None
    mutlipleResponses = []

    for sampleResponse in data:
        score = 0
        sampleInput = sampleResponse['input'].lower()
        sampleTokens = sampleInput.split()

        index = 0

        for token in tokens:
            if index >= len(sampleTokens):
                break

            if token == sampleTokens[index]:
                score += 1

            if token in sampleInput:
                score += 1

            index += 1

        # The more that matches the better the score it should get
        score = score / len(sampleTokens)

        if score > bestScore:
            bestScore = score
            bestResponse = sampleResponse['response']
            mutlipleResponses = [sampleResponse['response']]

        if score == bestScore:
            mutlipleResponses.append(sampleResponse['response'])

    if mutlipleResponses:
        return random.choice(mutlipleResponses)
    else:
        return bestResponse

while True:
    userInput = input('You: ')
    response = determineResponse(userInput)
    print(conversationMeta.get("botName", "Bot") + ':', response)