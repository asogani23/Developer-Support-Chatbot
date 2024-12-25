from flask import Flask, request, jsonify
from transformers import pipeline

# Initialize Flask app
app = Flask(__name__)

# Load the pre-trained language model for text generation
nlp = pipeline("text-generation", model="gpt2")

@app.route('/query', methods=['GET', 'POST'])
def query():
    if request.method == 'GET':
        return jsonify({"error": "Please use a POST request with a JSON payload"}), 405
    try:
        data = request.get_json()
        user_query = data.get("query", "")
        if not user_query:
            return jsonify({"error": "No query provided"}), 400

        # Generate response using GPT-2
        response = nlp(user_query, max_length=100, num_return_sequences=1)
        return jsonify({"response": response[0]['generated_text']})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)

