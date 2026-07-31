from pydantic import BaseModel
from src.schemas.movies_schema import MovieInShoppingCartResponseSchema
from typing import List


class CartResponseSchema(BaseModel):
    movies: List[MovieInShoppingCartResponseSchema] = []

    model_config = {"from_attributes": True}
