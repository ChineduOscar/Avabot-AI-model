from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
import re
import openai
from fuzzywuzzy import fuzz, process  # Add fuzzy matching for spelling mistakes
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()


# Load product data from JSON file
def load_products():
    with open("products.json", "r") as f:
        return json.load(f)

app = FastAPI()
products = load_products()

openai.api_key = os.getenv("API_KEY")

# Request model for user input
class UserRequest(BaseModel):
    query: str

# Function to filter products based on keywords, price range, and spelling variations
def filter_products(query, products):
    # Normalize query for flexible matching
    price_range = re.findall(r"\d{1,3}(?:,\d{3})*", query)
    lower_price, upper_price = None, None
    if len(price_range) == 2:
        lower_price, upper_price = [int(price.replace(",", "")) for price in price_range]

    keywords = query.lower().split()
    filtered_products = []

    # Fuzzy match product names to allow for minor spelling errors
    for product in products:
        product_name = product["name"].lower()
        name_match_score = process.extractOne(query, [product_name], scorer=fuzz.partial_ratio)
        if name_match_score and name_match_score[1] >= 70:  # Set a threshold for fuzzy matching
            if lower_price and upper_price:
                if lower_price <= product["price"] <= upper_price:
                    filtered_products.append(product)
            else:
                filtered_products.append(product)

    return filtered_products

# Generate responses using GPT-3 for conversational tone and basic greetings
def generate_conversational_response(query):
    # Friendly responses for greetings and introductions
    greeting_keywords = ["hello", "hi", "good morning", "good afternoon", "who are you"]
    if any(greeting in query for greeting in greeting_keywords):
        return "Hello! I’m Avabot, your shopping assistant here to help with all your shopping needs. Just ask me about products, prices, or anything else!"

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": query}],
            max_tokens=50,
            n=1,
            temperature=0.7,
        )
        return response.choices[0].message["content"].strip()
    except Exception:
        return "I'm having some trouble answering that right now. Please try again later."

# Endpoint to receive user query and respond accordingly
@app.post("/chatbot/")
async def chatbot_response(user_request: UserRequest):
    query = user_request.query.lower()

    # Check if the query is shopping-related or needs a friendly introduction
    shopping_keywords = ["buy", "price", "product", "purchase", "order", "specifications", "features", "details"]
    is_shopping_related = any(keyword in query for keyword in shopping_keywords)

    if is_shopping_related:
        # Handle shopping-related queries and provide all product data
        matching_products = filter_products(query, products)
        if not matching_products:
            return {"response": "Sorry, I couldn't find any products that match your request."}

        # Format the response to include full product details
        response = "Here are some products you might be interested in:\n"
        for product in matching_products:
            response += f"\n- {product['name']} - {product['price']} {product.get('currency', '₦')}"
            response += f"\nSpecifications: {product.get('specifications', 'N/A')}"
            response += f"\nFeatures: {product.get('features', 'N/A')}"
            response += f"\nDetails: {product.get('description', 'N/A')}\n"

        return {"response": response, "products": matching_products}
    else:
        # Friendly response for general or non-shopping questions
        conversational_response = generate_conversational_response(query)
        return {"response": conversational_response}
