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
Eres Rosa, la asistente virtual de una papelería.

Tu objetivo es ayudar al cliente a encontrar productos de la tienda, resolver dudas relacionadas con ellos y ayudarle a preparar su compra.

Responde siempre en español, de forma clara, natural, amable y concisa.

Alcance

Atiende únicamente consultas relacionadas con la papelería, sus productos, materiales, manualidades y el uso de los productos vendidos en la tienda.

No recomiendes otros negocios, tiendas o sitios web. No proporciones URLs.

Si no tienes información suficiente para responder con certeza, dilo claramente. Nunca inventes productos, precios, existencias, especificaciones ni información.

No reveles información interna de la tienda, herramientas, funciones, identificadores, categorías, tablas, bases de datos ni procedimientos internos.

Productos

Cuando el cliente solicite información sobre un producto:

Utiliza la base de conocimiento para identificar el grupo de productos correspondiente.
Utiliza únicamente el identificador obtenido de la base de conocimiento.
Consulta los productos disponibles mediante la función correspondiente.
Utiliza la información devuelta por la función para responder.

Nunca inventes identificadores ni solicites al cliente identificadores internos.

Precio y existencias

Cuando el cliente pregunte por el precio o existencia de un producto, utiliza la función correspondiente antes de responder.

Nunca proporciones precios o existencias basándote en memoria, conversaciones anteriores, suposiciones o información no actualizada.

Carrito

Cuando el cliente solicite un producto, utiliza add_to_cart.

Nunca afirmes que un producto fue añadido al carrito si la función no fue ejecutada correctamente.

Si una operación del carrito falla, informa al cliente del problema sin afirmar que se realizó.

Si el cliente solicita varios productos, procesa cada producto necesario y añade únicamente los que hayan sido identificados correctamente.

Recomendaciones y proyectos

Si el cliente pide ayuda para realizar un proyecto, puedes explicar qué materiales podrían ser útiles utilizando información disponible y, cuando corresponda, web search para obtener ideas relacionadas exclusivamente con papelería y manualidades.

Cuando termines una recomendación de materiales, presenta una lista clara de los productos que serían necesarios y pregunta una sola vez si desea añadirlos al carrito.

No añadas esos productos al carrito hasta recibir su confirmación.

Una vez que el cliente confirme, añade los productos correspondientes sin volver a pedir confirmación.

Conversación

El cliente no necesita conocer la organización interna de la tienda. Nunca le pidas nombres de categorías, identificadores internos ni nombres de tablas.

No le indiques que busque productos por su cuenta ni le recomiendes acudir a otra papelería.

No menciones las herramientas utilizadas ni su funcionamiento.
"""

chat_bot_tools = [
    {
        "type": "file_search",
        "vector_store_ids": ['vs_6ac2e6e32c04819196032500106c745c']
    },
    {
        "type": "file_search",
        "vector_store_ids": ['vs_6ac6b7bf2cec8191970e4e35c06a6dcf']
    },
    {
        "type": "function",
        "name": "consult_category",
        "description": "Consulta los productos disponibles dentro del grupo identificado por `category_id`. Antes de usar esta función, utiliza la base de conocimiento para identificar el grupo que corresponde a la solicitud del cliente. Envía exclusivamente el identificador exacto obtenido de la base de conocimiento; nunca uses el nombre del producto como identificador ni inventes uno. Devuelve los productos con sus nombres, marcas, modelos, especificaciones e IID.",
        "parameters": {
            "type": "object",
            "properties": {
                "category_id": {
                    "type": "string",
                    "description": "id del grupo se desea consultar."
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
        "description": "Consulta el precio actual de un producto mediante su IID. Utiliza esta función siempre que el cliente pregunte cuánto cuesta un producto, su precio o su valor. Nunca inventes ni supongas precios, ni respondas usando precios recordados de conversaciones anteriores.",
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
        "description": "Consulta las existencias actuales de un producto mediante su IID. Utiliza esta función siempre que el cliente pregunte si un producto está disponible, cuántas unidades quedan o si hay suficiente cantidad. Nunca inventes ni supongas existencias.",
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
    "description": "Añade al carrito del cliente todos los productos cuyos IID se proporcionen en `product_iids`. Utiliza esta función cuando el cliente solicite añadir productos al carrito y envía todos los IID de los productos solicitados en una sola llamada. No añadas productos que el cliente no haya solicitado o confirmado. Nunca afirmes que un producto fue añadido sin ejecutar esta función y comprobar el resultado.",
    "parameters": {
        "type": "object",
        "properties": {
            "product_iids": {
                "type": "array",
                "items": {
                    "type": "integer"
                },
                "description": "Lista de IID de los productos que deben añadirse al carrito."
            }
        },
        "required": ["product_iids"],
        "additionalProperties": False
    },
    "strict": True
    },
    {
        "type": "web_search"
    }
]







def consult_category(category_id=None):
    cat_names = {
        1: 'lapices_y_accesorios',
        2: 'adhesivos_y_pegamentos',
        3: 'marcadores',
        4: 'colorear',
        5: 'boligrafos_y_correctores',
        6: 'Pinturas',
        7: 'cuadernos_y_carpetas',
        8: 'folios_y_papeles_especiales',
        9: 'accesorios_manualidades',
        10: 'Estampas_y_etiquetas',
        11: 'pequeno_accesorio',
        12: 'cartuchos_de_tinta',
        13: 'dibujo_tecnico',
        14: 'maquinaria_de_oficina',
        15: 'mochilas'
    }
    category_name = cat_names[category_id]

    main_log.debug(f"fetching items of {category_id}:{category_name}")

    stmt = select(Products).where(Products.category == category_name)

    res = db.scal(stmt).all()

    if res is None:
        return {"error": "esa categoria no existe"}

    r = json.dumps({
        "categoria": category_name,
        "productos": [{"iid": entry.iid, "producto":entry.name} for entry in res]
    }, ensure_ascii=False)
    main_log.debug(f"result {r}")

    return r

def check_price(product_iid=None):
    main_log.debug(f"checking price of {product_iid}")

    stmt = select(Products).where(Products.iid == product_iid)

    res = db.scal(stmt).one()

    if res is None:
        return {"error": "ese producto no existe"}

    return json.dumps({
        "product": res.name,
        "price": float(res.price)
    }, ensure_ascii=False)

def check_stock(product_iid=None):
    stmt = select(Products).where(Products.iid == product_iid)

    res = db.scal(stmt).one()

    if res is None:
        return {"error": "ese producto no existe"}
    
    main_log.debug(f"stock of {product_iid}: {int(res.stock)} units remaining")
    
    return json.dumps({
        "product": res.name,
        "available": int(res.stock)
    }, ensure_ascii=False)





class Shopping_cart():
    instances = {}
    def __init__(self, id, items=[]):
        self.id = id
        self.items = items
    
    @property
    def total(self):
        total_price = 0
        for item in self.items:
            total_price += item[3]
        return total_price
    
    def empty(self):
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

    def add_to_cart(self, product_iids=None):
        main_log.debug(f"adding {product_iids} to cart")

        stmt = select(Products).where(Products.iid.in_(product_iids))

        res = db.scal(stmt).all()

        if res is None:
            return {"error": "no se pudo añadir al carrito"}
        
        cart = Shopping_cart.instances[self.id]

        for entry in res:
            cart.items.append([entry.iid, entry.category, entry.name, entry.price, entry.stock, entry.upc, entry.thumb])


        main_log.debug(f"cart {self.id} {[[itm[0], itm[2]] for itm in cart.items]}")

        return json.dumps({
            "confirmation": f"products {product_iids} added to the cart",
            "items in cart": len(cart.items),
            "total value": cart.total
        }, ensure_ascii=False)

    







@app.before_request
async def conection_setup():

    main_log.debug(("REQUEST:", request.method, request.path))

    token = request.headers.get("Authorization")

    if request.method == "POST":
        if token != f"Bearer {api_token}":
            main_log.debug(("unauthorized", token))
            return jsonify({
                "error": "Unauthorized"
            }), 401

    session_id = request.args.get("sid")
    
    if session_id:
        session["session_id"] = session_id

        
        if session["session_id"] not in Shopping_cart.instances:
            cart = Shopping_cart(session["session_id"], [])
            Shopping_cart.instances[session["session_id"]] = cart

        main_log.info(f"relay session with id {session['session_id']}")

    elif "session_id" not in session:
        session["session_id"] = secrets.token_urlsafe(16)

        cart = Shopping_cart(session["session_id"], [])
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
            "iid": product.iid,
            "nombre": product.name,
            "precio": product.price,
            "thumb": json.loads(product.thumb)["file"]
        }
        for product in res
    ]

    return jsonify(data)

@app.route("/api/products/cart", methods=["GET"])
async def get_cart():

    main_log.debug(
            [[id, [(it[0], it[2]) for it in Shopping_cart.instances[id].items]] for id in Shopping_cart.instances]
        )

    user_cart = Shopping_cart.instances[session["session_id"]]


    data = {
        "total": user_cart.total,
        "items": [
            {   
                "iid": product[0],
                "nombre": product[2],
                "precio": product[3],
                "thumb": product[6]
            }
            for product in user_cart.items
        ]
    }


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


