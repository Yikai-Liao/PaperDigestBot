Architecture Design Document
Overview
This document provides a detailed architecture design for a bot system that manages paper recommendation, summarization, and user interactions with external services and databases. The system uses Taskiq for asynchronous task management and communication between the Telegram Bot Entry (main entry) and the Dispatcher. It integrates GitHub Actions for scheduled tasks, such as daily updates to Arxiv embeddings, and leverages asyncio for non-blocking operations. The design is production-ready, scalable, and extensible.

System Components
1. Users' GitHub Repo

Description: The entry point where users store markdowns of research papers. PDFs are not stored here; they are downloaded on-demand from Arxiv.
Interaction: Feeds data into the system via the "Recommend" process, connecting to the AI Abstract module.
Output: Triggers the recommendation pipeline with markdowns and Arxiv identifiers (e.g., Arxiv IDs).

2. AI Abstract

Description: A module that processes PDFs (downloaded from Arxiv) into markdowns and generates abstracts using AI.
Inputs: Arxiv identifiers from Users' GitHub Repo, used to download PDFs on-demand.
Outputs: Markdowns and abstracts.
Connections: 
Sends processed data to the Dispatcher.
Archives data to the Own Static Website.


Note: PDFs are downloaded from Arxiv when needed and are not stored in the repository.

3. Own Static Website

Description: A static site for archiving processed abstracts and markdowns.
Input: Receives data from AI Abstract.
Purpose: Provides persistent storage and access for users.

4. Huggingface ArxivEmbedding

Description: A Huggingface dataset (daily updated) that contains the newest Arxiv papers metadatas and embeddings.

5. Huggingface PaperDigest

Description: A Huggingface dataset that stores that backup of the daily digest of all users who want to share their data.

6. GitHub Action ArxivEmbedding

Description: A GitHub Actions workflow that updates Arxiv embeddings daily.
Input: Scheduled trigger.
Output: Updates sent to Huggingface ArxivEmbedding.
Purpose: Keeps embeddings current.

7. podman compose

Description: Manages containers for dispatchers, vector databases, and bot entries. Lightweight and efficient, not computing-intensive.

Interaction: Links components to the Vector Database.
Note: Podman is used instead of Docker for container management, offering benefits like rootless operation and enhanced security.

8. Vector Database

Description: Stores and queries vector embeddings for similarity searches. Qdrant is used here with mmap for efficient memory management (1 GB at most).
Inputs: Embeddings from Huggingface ArxivEmbedding via podman compose.
Outputs: Results for similarity search queries from the Dispatcher.
Purpose: Enables efficient paper retrieval.

9. Dispatcher

Description: Central coordinator using Taskiq for asynchronous task management.
It could raise user github actions to run the recommendation pipeline and reuse all the existing summary. It could also call the vector database to find similar papers and send the results to the telegram bot entry.

Many outputs are stored to Cloudflare R2 here for persistent storage, like the ai summary and the extracted markdowns. And finally, the storage in R2 will be synced to Huggingface PaperDigest dataset daily.

Taskiq Integration: Manages tasks asynchronously, linking to Telegram Bot Entry.

10. Telegram Bot Entry

Description: Main user interface via Telegram, handling requests and responses.
Inputs: Tasks from Dispatcher (e.g., Reactions, Summary Task, Find Similars).
Outputs: Responses to Telegram Users.
Purpose: Facilitates user interaction using Taskiq.

11. Telegram Users

Description: End-users interacting via Telegram. (Identified by their Github ID)
Input: Sends requests to Telegram Bot Entry.
Output: Receives recommendations and summaries or similar papers.

12. Cloudflare R2

Description: Cloud storage for data backups.
Inputs: 
Daily backups from Huggingface PaperDigest.
Cached abstracts from Dispatcher.

Purpose: Ensures data availability.

13. Bitwarden Private Repo

Description: Secure storage for the github personal access token (PAT) used by the bot to access users' GitHub repositories.


Data Flow

Schedule Trigger: 

The pipeline is triggered in bot server according to user configed time schedule. And the paper recommendation action is called. (the PAT is stored in Bitwarden Private Repo)

Filtering by cache:

The system checks if the paper is already in the cache (Cloudflare R2). If not, it proceeds the id and other meta datas to the AI Abstract module.

AI Abstract and Markdown Generation:

Downloads the PDF from Arxiv using the provided Arxiv ID.
Extracts the abstract and converts the PDF into markdown format using marker
Generate the ai summary in json with the secret LLM API key stored in user's github repo secret.
Send the markdown and ai summary to the Dispatcher.

Dispatcher Processing:

Store all the newly generated markdowns and ai summaries to Cloudflare R2 for persistent storage.
Send the ai summary back to Telegram Bot Entry for user interaction.


Recommendation Feed in Telegram Bot Entry:

Convert the markdown into a telegram compatible format.
Send the markdown to the Telegram Bot Entry for user interaction.

User Interaction:
Telegram users receive the markdown and ai summary via the Telegram Bot Entry.
And add some 👍 or 👎 for the paper they see. This will be saved by Dispatcher into user's own preference data for next round generation.

User specified paper list summary:
Instead of recommendded by pipeline, users could seend a list of arxiv ids to the bot, and then the dispatcher. Then, dispatcher will treat it just like the recommended papers, check the R2 cache, send to Github Action to run the pipeline, and then send the markdown and ai summary back to the Telegram Bot Entry.

Similar Paper Search:

The user could send a list of arxiv ids to the bot, and then the dispatcher. Then, dispatcher will search the vector database for similar papers based on the embeddings. And the forward it to User's github actions, using their LLM to get a better similar recommendation results. Then, send them back to the Telegram Bot Entry.

Key Considerations

On-Demand PDF Download: PDFs are not stored in the repository; they are downloaded from Arxiv when needed, reducing storage requirements and ensuring access to the latest versions.
podman compose: Used for container management, providing a rootless and secure environment for running services.
Asynchronous Task Management: Taskiq enables efficient, non-blocking communication between the Dispatcher and Telegram Bot Entry.
Scalability: The system is designed to handle high loads, with components like the Vector Database and Cloudflare R2 ensuring performance and reliability.
Extensibility: Taskiq's modular design allows for easy replacement or addition of components, such as brokers or middlewares.