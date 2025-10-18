# Secure MPC Comparison Protocol

This project provides an implementation of a secure multi-party computation (MPC) protocol for comparing two numbers, `a` and `b`, held by two different parties. The comparison is performed by securely calculating the sign bit of the difference `a - b` without revealing the numbers themselves.

The implementation uses `torch.distributed` for orchestrating communication between worker nodes running in Docker containers. It does not rely on high-level MPC frameworks like CrypTen.

## Core Protocol

The protocol securely computes `a >= b` based on the following logic:

1.  **Problem Transformation**: The comparison `a >= b` is transformed into checking the sign of the subtraction `a - b`. If `a - b >= 0`, the condition is true.

2.  **Two's Complement**: To perform subtraction `a - b`, we use two's complement arithmetic, turning the operation into an addition: `a + (-b)`. Party 1, holding `b`, locally computes its two's complement representation.

3.  **Secret Sharing**: Each party secret-shares its value (`a` for Party 0, `-b` for Party 1) into two parts. They exchange one part with the other party. As a result, both parties hold one share of `a` and one share of `b`, but neither can reconstruct the original numbers.

4.  **Secure Addition Circuit**: The parties execute a secure binary addition circuit bit by bit, from least significant to most significant. The circuit is composed of secure full-adders.

5.  **Secure `AND` Gate**: The most critical component of the full adder is the secure `AND` operation, which is required to compute the carry bit. This is implemented using **Beaver Triples**. A trusted third-party (TTP) service provides shares of pre-computed random triples `(x, y, z)` where `z = x * y`. This allows the parties to compute the `AND` of their shared bits without revealing them.

6.  **Result**: The final output of the addition circuit is the most significant bit (the sign bit) of the sum `a - b`. The parties collaboratively reveal this single bit, which determines the result of the comparison.

## Project Structure

-   `worker.py`: The main entry point for each MPC worker. It parses arguments and dispatches tasks.
-   `tasks/collective.py`: Contains the core implementation of the secure comparison protocol (`compare` function) and its building blocks (`_secure_and`, `_secure_full_adder`).
-   `beaver.py`: A client for interacting with the Beaver Triple service (TTP).
-   `docker-compose.yml`: Defines the services for the two worker nodes.
-   `Dockerfile`: Specifies the Docker image for the worker environment.
-   `.env`: Configuration file for the TTP service URL.

## Getting Started

### Prerequisites

-   Docker
-   Docker Compose

### Running the Project

1.  **Configure TTP Service**:
    The Beaver Triple service is assumed to be running at an external IP address. Create a `.env` file and set the URL:
    ```
    TTP_URL=http://84.252.132.132:8090
    ```
    *(Note: This implementation uses a publicly available TTP for demonstration purposes. The source code for the TTP service can be found at https://github.com/12344321abc/beaver-ttp-service)*

2.  **Launch the Workers**:
    Execute the following command to build and run the two worker containers. The `compare` task is set by default in the `docker-compose.yml` file.
    ```bash
    docker-compose up --build
    ```
    The workers will start, perform the secure comparison on randomly generated numbers, and print the result.

## Development Cycle

To apply code changes, stop the running containers and rebuild the images:

```bash
docker-compose down
docker-compose up --no-deps --build