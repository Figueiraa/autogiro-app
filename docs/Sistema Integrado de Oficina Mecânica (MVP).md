# 🚗 Sistema Integrado de Oficina Mecânica (MVP)

## 📌 Descrição do Desafio

Uma oficina mecânica de médio porte, especializada em manutenção de veículos, enfrenta dificuldades para expandir seus serviços com qualidade e eficiência.

Atualmente, os processos são realizados de forma desorganizada, utilizando anotações manuais e planilhas, o que gera diversos problemas operacionais.

### ⚠️ Problemas Identificados

- Erros na priorização dos atendimentos  
- Falhas no controle de peças e insumos  
- Dificuldade em acompanhar o status dos serviços  
- Perda de histórico de clientes e veículos  
- Ineficiência no fluxo de orçamentos e autorizações  

---

## 🎯 Objetivo

Desenvolver um **Sistema Integrado de Atendimento e Execução de Serviços**, permitindo:

- Acompanhamento em tempo real do status da ordem de serviço
- Aprovação de orçamentos pelo cliente
- Gestão interna eficiente, organizada e segura

---

## 🧠 Proposta Técnica

Construção de um **MVP (Minimum Viable Product)** do back-end com foco em:

- Gestão de ordens de serviço
- Gestão de clientes e veículos
- Controle de peças e insumos

### 🏗️ Arquitetura

- Arquitetura em camadas (Layered Architecture)
- Aplicação de **Domain-Driven Design (DDD)**
- Back-end monolítico

---

## ⚙️ Funcionalidades

### 🔧 1. Criação da Ordem de Serviço (OS)

- Identificação do cliente (CPF/CNPJ)
- Cadastro de veículo:
  - Placa
  - Marca
  - Modelo
  - Ano
- Inclusão de serviços:
  - Ex: troca de óleo, alinhamento
- Inclusão de peças e insumos
- Geração automática de orçamento
- Envio do orçamento para aprovação do cliente

---

### 📊 2. Acompanhamento da Ordem de Serviço

#### Status da OS

- Recebida  
- Em diagnóstico  
- Aguardando aprovação  
- Em execução  
- Finalizada  
- Entregue  

#### Regras

- Atualização automática de status conforme ações do sistema
- Consulta disponível via API para clientes

---

### 🗂️ 3. Gestão Administrativa

#### CRUDs obrigatórios

- Clientes  
- Veículos  
- Serviços  
- Peças e insumos (com controle de estoque)  

#### Outras funcionalidades

- Listagem de ordens de serviço  
- Detalhamento de ordens de serviço  
- Monitoramento de tempo médio de execução  

---

## 🔐 Segurança e Qualidade

- Autenticação via JWT para rotas administrativas
- Validação de dados:
  - CPF/CNPJ
  - Placa de veículo
- Testes:
  - Testes unitários
  - Testes de integração
