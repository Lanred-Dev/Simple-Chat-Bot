import json

def addTrainingData(input, response):
    with open('data.json') as file:
        data = json.load(file)

    data.append({
        'input': input,
        'response': response
    })

    with open('data.json', 'w') as file:
        json.dump(data, file, indent=4)

while True:
    userInput = input('Input: ')
    response = input('Response: ')
    addTrainingData(userInput, response)