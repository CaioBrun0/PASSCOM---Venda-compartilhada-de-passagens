import time
from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import socket
import json
from collections import deque

app = Flask(__name__)
CORS(app)  # Habilita CORS para todas as rotas

# Rotas sob a responsabilidade do servidor 1
routes_server1 = {
    'Barreiras->Fortaleza->Salvador->Vitoria': 5,
    'Barreiras->Brasilia->Fortaleza->Salvador': 7,
    'Barreiras->Salvador->Brasilia->Manaus': 4,
}

# Lista de servidores
servers = [
    ('localhost', 8081),
]

# Token inicial
token = {
    "current_holder": 2,
}

current_server_id = 2

# Fila de solicitações pendentes
pending_requests = deque()

def process_purchase(route):
    if route in routes_server1 and routes_server1[route] > 0:
        routes_server1[route] -= 1
        return {"success": True, "remaining": routes_server1[route]}  # Retorna as passagens restantes
    else:
        return {"success": False, "message": "Passagem indisponível ou rota inválida."}

@app.route('/api/rota', methods=['POST'])
def descobrir_rotas():
    data = request.json
    origem = data.get('origem')
    destino = data.get('destino')
    
    rotas_disponiveis = {}
    
    for rota, passagens in routes_server1.items():
        if rota.startswith(origem) and rota.endswith(destino):
            rotas_disponiveis[rota] = {"passagens": passagens}

    return jsonify({"rotas": rotas_disponiveis})

@app.route('/api/comprar', methods=['POST', 'OPTIONS'])
def comprar_passagem():
    if request.method == 'OPTIONS':
        return jsonify({}), 200  # Responde às preflight requests com 200
    data = request.json
    rota = data.get('rota')
    
    if rota:
        if token['current_holder'] == 2:  # Verifica se o servidor possui o token
            print(f"Servidor 1: Processando compra para a rota: {rota}")
            resultado = process_purchase(rota)
            if resultado['success']:
                print(f"Compra realizada para a rota: {rota}")
                return jsonify({"success": True, "remaining": resultado['remaining']})
            else:
                print(f"Falha na compra: {resultado['message']}")
                return jsonify({"success": False, "message": resultado['message']})
        else:
            # Adiciona a solicitação à fila de pendências
            pending_requests.append(rota)
            print(f"Servidor 1: Solicitação para a rota {rota} adicionada à fila.")
            return jsonify({"success": False, "message": "Solicitação adicionada à fila."})
    else:
        return jsonify({"error": "Rota não especificada"}), 400

@app.route('/api/verificar_token', methods=['GET'])
def verificar_token():
    return jsonify({"has_token": token['current_holder'] == 2})  # Verifica se o servidor atual tem o token

def process_pending_requests():
    while True:
        if pending_requests:
            rota = pending_requests.popleft()  # Processa a próxima solicitação pendente
            print(f"Servidor 1: Processando solicitação pendente para a rota: {rota}")
            resultado = process_purchase(rota)
            if resultado['success']:
                print(f"Compra processada para a rota pendente: {rota}")
            else:
                print(f"Falha na compra da rota pendente: {rota}")

def start_token_server():
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('localhost', 8085))
                s.listen()
                print("Servidor de tokens está ouvindo...")
                while True:
                    conn, addr = s.accept()
                    print(f"Servidor 1: Conexão recebida de {addr}")
                    with conn:
                        token_data = json.loads(conn.recv(1024).decode('utf-8'))
                        print(f"Servidor 1: Token recebido: {token_data}")
                        print("Servidor 1: Processando token...")

                        process_pending_requests()  # Processa as solicitações pendentes

                        # Verifica se há mais servidores para passar o token
                        if len(servers) > 0:
                            token['current_holder'] = (token['current_holder'] % len(servers)) + 1
                            print(f"Servidor 1: Token passado para o Servidor {token['current_holder']}.")
                            send_token(token_data)
                        else:
                            print("Servidor 1: Não há outros servidores. Mantendo o token.")

        except Exception as e:
            print(f"Ocorreu um erro no servidor de tokens: {e}")
            time.sleep(3)


'''
def send_token(token_data):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if len(servers) > 0:
                next_server = servers[(token['current_holder'] - 1) % len(servers)]
                s.connect(next_server)
                s.sendall(json.dumps(token_data).encode('utf-8'))
                print(f"Servidor 1: Token enviado para {next_server}.")
            else:
                print("Servidor 1: Não há servidores para enviar o token.")
    except Exception as e:
        print(f"Ocorreu um erro ao enviar o token: {e}")

'''
def send_token(token_data):
    try:
        if len(servers) > 0:
            # Determina o próximo servidor com base no `current_holder`
            next_server = servers[token['current_holder'] - 1]
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(next_server)
                s.sendall(json.dumps(token_data).encode('utf-8'))
                print(f"Token enviado para o próximo servidor {next_server}.")
        else:
            print("Nenhum servidor disponível para enviar o token.")
    except Exception as e:
        print(f"Erro ao enviar o token: {e}")



def iniciar_token_thread():
    thread = threading.Thread(target=start_token_server)
    thread.start()

if __name__ == '__main__':
    iniciar_token_thread()
    app.run(port=8082, debug=True)  # Servidor escutando na porta 8081