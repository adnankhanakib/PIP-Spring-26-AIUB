import json
import os

class Memory:
    def __init__(self):
        self.filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "memory.json")
        self.data = self.load_data() or {} 
        if "memoryData" not in self.data:
            self.data["memoryData"] = {"subjects": [], "usernames": [], "sendTo": []}
        if "subjects" not in self.data["memoryData"]:
            self.data["memoryData"]["subjects"] = []

    def load_data(self):
        try:
            with open(self.filename, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return None

    def save_data(self):
        with open(self.filename, 'w') as file:
            json.dump(self.data, file, indent=2)

    def get(self, key):
        return self.data.get("memoryData")[key]

    def set(self, key, value):
        self.data[key] = value
        self.save_data()

    def delete(self, key):
        if key in self.data:
            del self.data[key]
            self.save_data()

    def add_to(self, key, value):
        lst = self.data["memoryData"].setdefault(key, [])
        if value and value not in lst:
            lst.append(value)
            self.save_data()

    def add_subject(self, subject):
        self.add_to("subjects", subject)