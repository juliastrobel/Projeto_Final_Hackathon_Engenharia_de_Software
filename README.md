[![LOGO](./static/email.png)](https://hackathon-ifpr.up.railway.app/)

# Hackathon IFPR Pinhais - [Website do projeto](https://hackathon-ifpr.up.railway.app/)

Sistema de apoio ao 1º Hackathon do curso de Ciência da Computação do IFPR Campus Pinhais, desenvolvido como projeto integrador da disciplina **Engenharia de Software I**.

O sistema cobre todo o ciclo do evento: inscrição de equipes, verificação automatizada de legitimidade das submissões via GitHub, avaliação pela banca examinadora e divulgação pública dos resultados.

📄 Para decisões de design mais detalhadas, consulte a [Wiki do projeto](../../wiki).

---

### Tecnologias e Ferramentas

#### Backend & Frameworks
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Uvicorn](https://img.shields.io/badge/Uvicorn-4053D6?style=for-the-badge&logo=uvicorn&logoColor=white)
![Jinja](https://img.shields.io/badge/Jinja2-B41717?style=for-the-badge&logo=jinja&logoColor=white)
![HTTPX](https://img.shields.io/badge/HTTPX-00599C?style=for-the-badge&logo=python&logoColor=white)

#### Banco de Dados
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

#### Frontend
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![Lucide Icons](https://img.shields.io/badge/Lucide_Icons-F56565?style=for-the-badge&logo=lucide&logoColor=white)

#### Serviços & Integrações
![Brevo](https://img.shields.io/badge/Brevo-0080FF?style=for-the-badge&logo=brevo&logoColor=white)
![Railway](https://img.shields.io/badge/Railway-131415?style=for-the-badge&logo=railway&logoColor=white)
![GitHub API](https://img.shields.io/badge/GitHub_API-181717?style=for-the-badge&logo=github&logoColor=white)

---

## Como rodar localmente

```bash
# clonar o repositório
git clone https://github.com/juliastrobel/Projeto_Final_Hackathon_Engenharia_de_Software.git
cd Projeto_Final_Hackathon_Engenharia_de_Software

# criar e ativar o ambiente virtual
python3 -m venv venv
source venv/bin/activate

# instalar as dependências
pip install -r requirements.txt

# configurar as variáveis de ambiente
cp .env.example .env
# preencher o .env com os valores reais

# rodar a aplicação
uvicorn app.main:app --reload
```

Acesse `http://localhost:8000` no navegador.

---

## Equipe

- **regra de negócio, APIs, banco de dados e servidor.**: Isaque Cortina Pires
- **design visual, telas, navegação e consumo das APIs**: Julia Pinheiro Strobel

---

## Licença

Este projeto está licenciado sob os termos da licença MIT.
