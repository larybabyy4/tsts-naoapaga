import ctypes
from ctypes import wintypes

# Função para exibir a caixa de erro do Windows
def mostrar_erro_fake():
    MessageBox = ctypes.windll.user32.MessageBoxW
    MessageBox(
        None,
        "O seu computador foi infectado por um vírus grave!\n"
        "Todos os seus arquivos foram criptografados.\n"
        "Para recuperar, envie R$ 5.000 em Bitcoin para a carteira abaixo.\n\n"
        "Just kidding... ou não? 😈",
        "Erro crítico do Windows",
        0x10 | 0x00  # MB_ICONSTOP (ícone de erro) + MB_OK
    )

# Executa a janela de erro
mostrar_erro_fake()
