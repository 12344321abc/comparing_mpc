# Comparing MPC

A sample project demonstrating p2p and collective operations in `torch.distributed`.

## Prerequisites

- Docker
- Docker Compose

## Getting Started

1.  **Environment Configuration:**

    Create a `.env` file in the project root and configure the `TTP_URL`:

    ```
    TTP_URL=http://beaver-ttp:8080
    ```

2.  **Running the Workers:**

    Each worker is defined as a service in the `docker-compose.yml` file. To specify which task a worker should execute, modify the `command` in its service definition.

    ```yaml
    command: python -m worker --rank <WORKER_RANK> --world_size <NUM_WORKERS> call <dotted.path.to:task>
    ```

    -   `<WORKER_RANK>`: The rank of the worker (0, 1, ...).
    -   `<NUM_WORKERS>`: The total number of workers.
    -   `<dotted.path.to:task>`: The path to the function to be executed (e.g., `tasks.collective:compare`).

3.  **Launch:**

    Use Docker Compose to build and run the containers:

    ```bash
    docker-compose up --build
    ```

## Development

To apply code changes, stop the running containers and rebuild the images:

```bash
docker-compose down
docker-compose up --build
```

## Testing

To run the Beaver client tests:

```
python3 test_beaver.py
```