import json

def addTrainingData(input, response):
    with open('samples.json') as file:
        samples = json.load(file)

    samples.append({
        'input': input,
        'response': response
    })

    with open('samples.json', 'w') as file:
        json.dump(samples, file, indent=4)

while True:
    userInput = input('Input: ')
    response = input('Response: ')
    addTrainingData(userInput, response)