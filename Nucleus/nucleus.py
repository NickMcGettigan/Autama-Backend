"""
This file contains a class to build and chat with an autama. This file borrows some
code from HuggingFace Inc.'s open source project. The code can be found here:
https://github.com/huggingface/transfer-learning-conv-ai/blob/master/interact.py
"""

import logging
import random
from argparse import ArgumentParser
from itertools import chain
from pprint import pformat

import torch

from transformers import OpenAIGPTLMHeadModel, OpenAIGPTTokenizer, GPT2LMHeadModel, GPT2Tokenizer
from Nucleus.train import add_special_tokens_
from Nucleus.utils import get_dataset, download_pretrained_model

from Nucleus.interact import sample_sequence


class Nucleus:
    def __init__(self, temperature = 0.7, top_k = 0, top_p = 0.9):
        self.__temperature = temperature
        self.__top_k = top_k
        self.__top_p = top_p
        self.__history = [] # For conversation

        parser = ArgumentParser()
        parser.add_argument("--dataset_path", type=str, default="",
                            help="Path or url of the dataset. If empty download from S3.")
        parser.add_argument("--dataset_cache", type=str, default='./dataset_cache',
                            help="Path or url of the dataset cache")
        parser.add_argument("--model", type=str, default="openai-gpt", help="Model type (openai-gpt or gpt2)",
                            choices=['openai-gpt', 'gpt2'])  # anything besides gpt2 will load openai-gpt
        parser.add_argument("--model_checkpoint", type=str, default="", help="Path, url or short name of the model")
        parser.add_argument("--max_history", type=int, default=2,
                            help="Number of previous utterances to keep in history")
        parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu",
                            help="Device (cuda or cpu)")

        parser.add_argument("--no_sample", action='store_true', help="Set to use greedy decoding instead of sampling")
        parser.add_argument("--max_length", type=int, default=20, help="Maximum length of the output utterances")
        parser.add_argument("--min_length", type=int, default=1, help="Minimum length of the output utterances")
        parser.add_argument("--seed", type=int, default=0, help="Seed")
        parser.add_argument("--temperature", type=int, default=self.__temperature, help="Sampling softmax temperature")
        parser.add_argument("--top_k", type=int, default=self.__top_k,
                            help="Filter top-k tokens before sampling (<=0: no filtering)")
        parser.add_argument("--top_p", type=float, default=self.__top_p,
                            help="Nucleus filtering (top-p) before sampling (<=0.0: no filtering)")
        self.__args = parser.parse_args()

        logging.basicConfig(level=logging.INFO)
        self.__logger = logging.getLogger(__file__)
        self.__logger.info(pformat(self.__args))

        if self.__args.model_checkpoint == "":
            if self.__args.model == 'gpt2':
                raise ValueError("Interacting with GPT2 requires passing a finetuned model_checkpoint")
            else:
                self.__args.model_checkpoint = download_pretrained_model()

        if self.__args.seed != 0:
            random.seed(self.__args.seed)
            torch.random.manual_seed(self.__args.seed)
            torch.cuda.manual_seed(self.__args.seed)

        self.__logger.info("Get pretrained model and tokenizer")
        tokenizer_class, model_class = (GPT2Tokenizer, GPT2LMHeadModel) if self.__args.model == 'gpt2' else (
        OpenAIGPTTokenizer, OpenAIGPTLMHeadModel)
        self.__tokenizer = tokenizer_class.from_pretrained(self.__args.model_checkpoint)
        self.__model = model_class.from_pretrained(self.__args.model_checkpoint)
        self.__model.to(self.__args.device)
        add_special_tokens_(self.__model, self.__tokenizer)

    # A method for generating one personality at a time
    def generate_personality(self):
        self.__logger.info("Sample a personality")
        dataset = get_dataset(self.__tokenizer, self.__args.dataset_path, self.__args.dataset_cache)
        personalities = [dialog["personality"] for dataset in dataset.values() for dialog in dataset]
        personality = random.choice(personalities)
        return personality

    # A method to display personality
    def display_personality(self, personality: list):
        self.__logger.info("Selected personality: %s", self.__tokenizer.decode(chain(*personality)))

    # A method to converse with an Autama by taking in Autama's personality and user's input
    def converse_with(self, personality: list, user_input: str):
        self.__history.append(self.__tokenizer.encode(user_input))
        with torch.no_grad():
            out_ids = sample_sequence(personality, self.__history, self.__tokenizer, self.__model, self.__args)
        self.__history.append(out_ids)
        self.__history = self.__history[-(2 * self.__args.max_history + 1):]
        nucleus_output = self.__tokenizer.decode(out_ids, skip_special_tokens=True)
        return nucleus_output
