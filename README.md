# LongChain / LangGraph SQL Agent Demo

This repository demonstrates the use of LangChain and LangGraph for SQL query generation, execution and validation.

## Database Schema

The project uses a relational database with the following tables:

| Table Name | Columns |
|------------|---------|
| Users      | id, email, full_name |
| Products   | id, name |
| Orders     | id, date, quantity, amount, product_id, user_id |

### Relationships
- A User can have multiple Orders (one-to-many)
- A Product can be in multiple Orders (one-to-many)
- An Order belongs to one User and one Product (many-to-one for both, not unique)

This schema allows for efficient querying of order data, including information about the users who placed the orders and the products that were ordered.

## Environment Setup

Before running the project, you need to set up your environment variables. Copy the `.env.example` file to `.env` and fill in the required values:

```
ENV=.env
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASS=your_database_password
DB_HOST=db
LOGGING_LEVEL=ERROR
OPENAI_API_KEY=your_openai_api_key
```


## Project Setup

To set up and run the project, follow these steps:

1. Build the Docker images:
   ```
   docker compose build
   ```

2. Start the database:
   ```
   docker compose up -d db
   ```

3. Run database migrations:
   ```
   docker compose up alembic-upgrade
   ```

4. Apply fixtures to generate test data:
   ```
   docker compose -p agent up apply-fixtures
   ```

## API Endpoints

The project provides two main endpoints:

1. `/chain_query` - Uses ChainSQLAgent
2. `/graph_query` - Uses GraphSQLAgent

Both endpoints accept POST requests with a JSON body containing a `query` field.

### Request Format

```json
{
  "query": "What is the total revenue for the year 2023?"
}
```


### Response Format

The API responds with a JSON object containing two fields:

- `result`: The answer to the query in natural language
- `raw_sql`: The SQL query generated to answer the question

Example:

```json
{
  "result": "The revenue for May 2024 is $2,471,364.08.",
  "raw_sql": "SELECT SUM(amount) AS total_revenue\nFROM orders\nWHERE DATE_PART('year', date) = 2024 AND DATE_PART('month', date) = 5;"
}
```


This example demonstrates how the system takes a natural language query, generates the appropriate SQL, executes it, and returns both the result and the raw SQL query used.

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).