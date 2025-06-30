import streamlit as st

st.set_page_config(page_title="Calculadora de IMC")

st.title("🧮 Calculadora de IMC")

# Entrada de dados
peso = st.number_input("Digite seu peso (kg)", min_value=0.0, step=0.1)
altura = st.number_input("Digite sua altura (m)", min_value=0.0, step=0.01)

if peso > 0 and altura > 0:
    imc = peso / (altura ** 2)
    st.write(f"Seu IMC é: **{imc:.2f}**")

    if imc < 18.5:
        st.warning("Abaixo do peso")
    elif imc < 25:
        st.success("Peso normal")
    elif imc < 30:
        st.warning("Sobrepeso")
    else:
        st.error("Obesidade")
else:
    st.info("Informe peso e altura para calcular.")
