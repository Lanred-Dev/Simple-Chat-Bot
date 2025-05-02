import json

def add_sample(message: str, response: str):
    with open('samples.json') as file:
        SAMPLES = json.load(file)

    SAMPLES.append({
        "input": message,
        "response": response
    })

    with open('samples.json', 'w') as file:
        json.dump(SAMPLES, file, indent=4)

def prompt_mode():
    print("""
    # (1) 'train' - Train the bot with samples\n
    # (2) 'quit' - Exit the program
    """)

    mode = input("What mode do you want to enter? (train/quit): ")

    print(f"{mode} mode selected.\n")

    if mode == 'train':
        print("Samples are formatted as: \nInput: <user input> \nResponse: <bot response>\n")

        while True:
            message = input('Input: ')
            response = input('Response: ')
            add_sample(message, response)
    elif mode == 'quit':
        print("Exiting the program.")
        exit()

prompt_mode()