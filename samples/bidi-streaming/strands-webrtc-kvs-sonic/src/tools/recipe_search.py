"""Recipe search tool using Bedrock Knowledge Base."""

import logging

import boto3
from botocore.exceptions import ClientError
from strands import tool

from config import AWS_REGION, BEDROCK_KB_ID

logger = logging.getLogger(__name__)

bedrock_agent_runtime = boto3.client(
    "bedrock-agent-runtime",
    region_name=AWS_REGION,
)


@tool
def search_recipes(query: str) -> str:
    """Search the recipe knowledge base for recipes matching the query.

    Use this tool whenever a user asks about recipes, ingredients, or cooking methods.
    The knowledge base contains a personal recipe collection.

    Args:
        query: Natural language search query about recipes
    """
    if not BEDROCK_KB_ID:
        return "Error: Knowledge Base ID not configured. Set BEDROCK_KB_ID environment variable."

    logger.info("search_recipes: raw query=%r", query)

    try:
        def retrieve(configuration_key):
            return bedrock_agent_runtime.retrieve(
                knowledgeBaseId=BEDROCK_KB_ID,
                retrievalQuery={"text": query},
                retrievalConfiguration={
                    configuration_key: {
                        "numberOfResults": 3,
                    }
                },
            )

        try:
            response = retrieve("vectorSearchConfiguration")
        except ClientError as vector_error:
            if vector_error.response.get("Error", {}).get("Code") != "ValidationException":
                raise
            logger.info("Vector search rejected; trying managed search configuration")
            try:
                response = retrieve("managedSearchConfiguration")
            except ClientError:
                raise vector_error

        results = response.get("retrievalResults", [])
        if not results:
            return "No recipes found matching that query."

        # Group chunks by source file so multi-chunk recipes are reassembled
        source_chunks = {}
        for r in results:
            score = r.get("score", 0)
            if score < 0.3:
                continue

            text = r.get("content", {}).get("text", "").strip()
            if not text:
                continue

            source = r.get("location", {}).get("s3Location", {}).get("uri", "")
            source_name = source.split("/")[-1].replace(".md", "") if source else "unknown"

            if source not in source_chunks:
                source_chunks[source] = {"name": source_name, "score": score, "texts": []}
            source_chunks[source]["texts"].append(text)
            if score > source_chunks[source]["score"]:
                source_chunks[source]["score"] = score

        if not source_chunks:
            logger.info("search_recipes: no results above score threshold for query=%s", query)
            return "No recipes found with a strong enough match. Try a different search."

        # Return top 3 by score
        top = sorted(source_chunks.values(), key=lambda e: e["score"], reverse=True)[:3]
        chunks = []
        for entry in top:
            merged = "\n\n".join(entry["texts"])
            chunks.append(f"Recipe: {entry['name']} (score: {entry['score']:.2f})\n{merged}")

        result = f"Found {len(top)} recipe(s):\n\n" + "\n\n".join(chunks)
        logger.info("search_recipes: query=%s, found=%d recipes: %s", query, len(top),
                     [(e['name'], f"{e['score']:.2f}") for e in top])
        return result

    except Exception as e:
        logger.exception("Error searching recipe knowledge base")
        return f"Error searching recipes: {e}"
