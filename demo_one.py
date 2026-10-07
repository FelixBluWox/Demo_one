from utils import Wox_log, error_form, stdout_debug_handler
from sqlalchemy import select
from openai import OpenAI 
from flask import Flask, request, jsonify, session
from dotenv import load_dotenv
from colorama import Fore
from os import getenv
from database import Database, Products
from asyncio import to_thread
import requests, json, secrets
from dataclasses import dataclass
from typing import ClassVar, Dict
from waitress import serve
from flask_cors import CORS


main_log = Wox_log('main', color=Fore.LIGHTCYAN_EX, std_handler=stdout_debug_handler)

load_dotenv('./secrets.env')
token_sc = getenv("openai_key_sc")
token_fx = getenv("openai_key_fx")
api_token = getenv("self_token")
mod_token = getenv("admon_token")

gpt_client = OpenAI(api_key=token_sc)

db = Database()

app = Flask(__name__)
CORS(
    app,
    resources={r"/api/*": {
        "origins": "*"
    }},
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "OPTIONS"]
)

app.secret_key = getenv("flask_secret")


agent_prompt = """
Eres Rosa la asistente virtual de una papelería. Que desea ayudar a los clientes a encontrar los insumos necesarios en nuestra tienda.

Ayuda a los clientes a encontrar productos en la papeleria y resolver
preguntas relacionadas con el uso de ellos.

Enfocate solo en productos que vendamos en esta papeleria.

Puedes dar respuestas generales e información, pero en ningún caso puedes responder con links o url para ir a otras páginas ni incitar al cliente a ir a otro negocio. Responde solo con información verificada. Para responder utiliza un tono amable y confiable que refleje creatividad.

Si no puedes encontrar una respuesta fiable y comprobable, responde que No tienes información suficiente para responder eso con certeza.. Nunca inventes datos ni des suposiciones ni supongas información.

Usa File Search para consultar la base de conocimiento para deducir en que tabla en la base de datos pueden estar los productos necesarios. prioriza la informacion de las funciones.

En file search, tienes categoria: el nombre de una tabla en la base de datos, contenidos: el tipo de cosas que hay en esa tabla, para usar la funcion de consult_category debes enviar el nombre en la tabla que nececitas ver.

NO ALUCINES TABLAS, el nombre de las tablas que tienes en el file search es ese como esta textual mente

Usa la funcion consult_category para obtener informacion de todos los productos disponibles en la tienda en esa tabla. esto te dara nombres detallados, marca, modelo y espescificaciones tecnicas de los productos.

Cuando ya hayas identificado los productos que el cliente va a comprar añadelos al carrito.

Si no encuentras un producto en la tabla que pensabas, busca en las tablas de accesorios.

Usa la funcion web_search unicamente para  darle ideas sobre su proyecto al cliente si lo pide o para aclarar dudas del cliente, con la estricta restriccion de que sea en base a papeleria y manualidades.

Recuerda eres una asociada de ventas, tu objetivo es brindarle buena atencion al cliente y vender los productos del negocio.

Nunca inventes información sobre productos o existencias.

Responde en español de manera clara, natural y concisa.

No respondas peticiones del cliente que no tengan que ver con la papeleria, en cambio reiterale que estas a su servicio para brindarle los materiales que necesite para hace volar su imaginacion.

No expongas el uso de las funciones directamente al cliente

Tienes prohibido hacer cualquier mencion o referencia a las tablas. 

Si el cliente pregunta por productos en especifico, usa las funciones para darle informacion exacta.

Toma un tono calido y energetico, con entusiasmo por darle al cliente los productos que necesita.
"""

chat_bot_tools = [
    {
        "type": "file_search",
        "vector_store_ids": ['vs_6ac2e6e32c04819196032500106c745c']
    },
    {
        "type": "function",
        "name": "consult_category",
        "description": "Consulta los productos disponibles de una categoría.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Nombre textual de la tabla en la base de datos que se desea consultar."
                }
            },
            "required": ["category"],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "type": "function",
        "name": "check_price",
        "description": "consulta el precio de un producto.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_iid": {
                    "type": "integer",
                    "description": "iid del producto a consultar."
                }
            },
            "required": ["product_iid"],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "type": "function",
        "name": "check_stock",
        "description": "consulta la disponibilidad de un producto.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_iid": {
                    "type": "integer",
                    "description": "iid del producto a consultar."
                }
            },
            "required": ["product_iid"],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "type": "function",
        "name": "add_to_cart",
        "description": "añade un proucto al carrito del cliente.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_iid": {
                    "type": "integer",
                    "description": "iide del producto a agregar."
                }
            },
            "required": ["product_iid"],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "type": "web_search"
    }
]







def consult_category(category=None):
    main_log.debug(f"fetching items of {category}")

    stmt = select(Products).where(Products.category == category)

    res = db.scal(stmt).all()

    if res is None:
        return {"error": "esa categoria no existe"}

    r = str({
        "categoria": category,
        "productos": [{"iid": entry.iid, "producto":entry.name} for entry in res]
    })
    main_log.debug(f"result {r}")

    return r

def check_price(product_iid=None):
    main_log.debug(f"checking price of {product_iid}")

    stmt = select(Products).where(Products.iid == product_iid)

    res = db.scal(stmt).one()

    if res is None:
        return {"error": "ese producto no existe"}
    
    r = str({
        "product": res.name,
        "price": float(res.price)
    })
    main_log.debug(f"result {r}")

    return r

def check_stock(product_iid=None):
    stmt = select(Products).where(Products.iid == product_iid)

    res = db.scal(stmt).one()

    if res is None:
        return {"error": "ese producto no existe"}
    
    main_log.debug(f"stock of {product_iid}: {int(res.stock)} units remaining")

    r = str({
        "product": res.name,
        "available": int(res.stock)
    })
    main_log.debug(f"result {r}")
    
    return r





@dataclass
class Shopping_cart:
    instances: ClassVar[Dict[str, 'Shopping_cart']] = {}
    
    id: str
    items: list = None
    
    @property
    def total():
        total_price = 0
        for item in self.items:
            total_price += item[3]
        return total_price
    
    def empty():
        self.list = []



class Chat_bot():
    instances = {}
    def __init__(self, id):
        self.id = id
        self.conversation = gpt_client.conversations.create()
        self.initialized = False
        self.func_queue = []
        self.functions = {
            "consult_category": lambda args: consult_category(**args),
            "check_price": lambda args: check_price(**args),
            "check_stock": lambda args: check_stock(**args),
            "add_to_cart": lambda args: self.add_to_cart(**args)
        }

    def message(self, input):
        if not self.initialized:
            response = gpt_client.responses.create(
                model="gpt-4o-mini",
                conversation=self.conversation.id,
                instructions=agent_prompt,
                input=input,
                tools=chat_bot_tools
            )

            self.initialized = True
            self.func_queue += [item for item in response.output if item.type == "function_call"]
            main_log.debug(f"bot {self.id} first interaction")
        else:
            response = gpt_client.responses.create(
                model="gpt-4o-mini",
                conversation=self.conversation.id,
                input=input
            )

            self.func_queue += [item for item in response.output if item.type == "function_call"]
        
        main_log.debug(f"bot {self.id}:     {response.output_text}")
        return response
    
    def process_funcs(self):
        main_log.debug(f"bot {self.id} runing queue: {self.func_queue}")
        outputs = []
        for i in range(len(self.func_queue)):
            func_call = self.func_queue.pop()
            main_log.debug(f"corriendo funcion {func_call.name} < {func_call.arguments} : {type(func_call.arguments)}")
            outputs.append({
                "type": "function_call_output",
                "call_id": func_call.call_id,
                "output": self.functions[func_call.name](json.loads(func_call.arguments))
            })

        return self.message(outputs)

    def add_to_cart(self, product_iid=None):
        main_log.debug(f"adding {product_iid} to cart")

        stmt = select(Products).where(Products.iid == product_iid)

        res = db.scal(stmt).all()

        if res is None:
            return {"error": "ese producto no existe"}
        
        cart = Shopping_cart.instances[self.id]

        cart.items.append([res.iid, res.category, res.name, res.price, res.stock, res.upc, res.thumb])

        main_log.debug(f"cart {cart.items}")

        return str({
            "confirmation": f"product {res.iid} added to the cart",
            "items in cart": len(cart.items),
            "total value": cart.total
        })

    







@app.before_request
async def conection_setup():

    main_log.debug(("REQUEST:", request.method, request.path))

    #if request.method == "OPTIONS":
    #    return "", 204

    token = request.headers.get("Authorization")

    if request.method == "POST":
        if token != f"Bearer {api_token}":
            main_log.debug(("unauthorized", token))
            return jsonify({
                "error": "Unauthorized"
            }), 401



    if "session_id" not in session:
        session["session_id"] = secrets.token_urlsafe(16)

        cart = Shopping_cart(session["session_id"])
        Shopping_cart.instances[session["session_id"]] = cart

        main_log.info(f"new session with id {session['session_id']}")
        
    else:
        main_log.debug(f"conection with session id {session['session_id']}")
    
@app.after_request
def add_cors(response):
    
    origin = request.headers.get("Origin")
    response.headers["skip_zrok_interstitial"] = "true"
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"

    main_log.debug(f"respuesta {response}")
    return response

@app.route("/api/chat", methods=["POST"])
async def chat_endpoint():
    data = request.get_json()
    message = [{"role": "user", "content": data.get("message")}]

    if not message:
        return jsonify({"error": "No message provided"}), 400

    if session["session_id"] not in Chat_bot.instances:
        chatbot = Chat_bot(session["session_id"])
        Chat_bot.instances[session["session_id"]] = chatbot
    else:
        chatbot = Chat_bot.instances[session["session_id"]]
    

    main_log.debug(f"incoming message:\n {data}\n {message}")



    response = await to_thread(chatbot.message, message)
    if len(chatbot.func_queue) > 0:
        response = await to_thread(chatbot.process_funcs)
    

    return jsonify({
        "response": response.output_text
    })



@app.route("/api/debug", methods=["POST"])
async def debug_endpoint():

    token = request.headers.get("X-api-token")

    if request.method == "POST":
        if token != f"{mod_token}":
            main_log.debug(("unauthorized", token))
            return jsonify({
                "error": "Unauthorized"
            }), 401

    data = request.get_json()
    message = [{"role": "developer", "content": data.get("message")}]

    if not message:
        return jsonify({"error": "No message provided"}), 400

    if session["session_id"] not in Chat_bot.instances:
        chatbot = Chat_bot(session["session_id"])
        Chat_bot.instances[session["session_id"]] = chatbot
    else:
        chatbot = Chat_bot.instances[session["session_id"]]
    

    main_log.debug(f"incoming message:\n {data}\n {message}")



    response = await to_thread(chatbot.message, message)
    if len(chatbot.func_queue) > 0:
        response = await to_thread(chatbot.process_funcs)
    

    return jsonify({
        "response": response.output_text
    })



@app.route("/api/products/all", methods=["GET"])
async def get_all_products():

    stmt = select(Products)

    res = db.scal(stmt).all()

    data = [
        {
            "nombre": product.name,
            "precio": product.price,
            "thumb": dict(product.thumb)["file"]
        }
        for product in res
    ]

    return jsonify(data)

@app.route("/api/products/price", methods=["GET"])
async def get_price():
    p_id = request.args.get("id", "Flask")
    return await to_thread(check_price, p_id)
    

@app.route("/api/products/stock", methods=["GET"])
async def get_stock():
    p_id = request.args.get("id", "Flask")
    return await to_thread(check_stock, p_id)

@app.route("/api/test", methods=["POST"])
async def test():
    return jsonify({
                "response": "success"
            }), 200






if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=8080)


