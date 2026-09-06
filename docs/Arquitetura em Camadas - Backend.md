# Arquitetura em Camadas - Backend

## Arquitetura em Camadas (Layered Architecture)
Documentação sobre o uso de Arquitetura em Camadas  
(Controller / Service / Repository) em projetos FastAPI.

## Quando usar

É um tipo de Arquitetura simples, clara e fácil de manter.

- Desenvolvimento de APIs REST  
- Projetos que precisam crescer com organização  

## Estrutura de pastas

app/
│
├── main.py
│
├── core/
│ ├── config.py
│ ├── database.py
│ └── dependencies.py
│
├── controllers/
│ └── user_controller.py
│
├── services/
│ └── user_service.py
│
├── repositories/
│ └── user_repository.py
│
├── models/
│ └── user_model.py
│
├── schemas/
│ └── user_schema.py
│
└── exceptions/
└── domain_exceptions.py

## Fluxo da aplicação

Nunca pular camadas.

HTTP Request  
→ Controller  
→ Service  
→ Repository  
→ Database  

## Camadas e responsabilidades

### Controller
- Lida apenas com HTTP  
- Recebe request e retorna response  
- Define status code  
- Chama o Service  
- Não acessa banco  
- Não contém regra de negócio  

### Service
- Contém regras de negócio  
- Orquestra o fluxo da aplicação  
- Decide o que pode ou não pode  
- Chama repositórios  
- Não conhece HTTP  
- Não lança HTTPException  

### Repository
- Acesso ao banco de dados  
- Encapsula ORM / SQL  
- Retorna dados persistidos  
- Não contém regra de negócio  

### Model
- Representa tabelas do banco (ORM)  

### Schema
- Apenas estrutura de dados  
- Sem lógica de negócio  
- Entrada e saída da API (Pydantic)  
- Validação de dados externos  
- Usado no Controller  

### Exceptions
- Exceções de negócio (NotFound, Conflict, etc)  
- Criadas no Service  
- Mapeadas para HTTP no Controller ou handler global  

## Regras da Arquitetura em Camadas

Quebrou alguma regra → code review não passa.

1. Controller nunca acessa banco  
2. Repository nunca contém regra de negócio  
3. Service nunca retorna HTTPException  
4. Nunca pular camadas  