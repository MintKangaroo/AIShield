"""LLM red-team track: a separate threat and metric contract from the image engine.

This package never imports the image attack code and shares no metrics with it. An
LLM is tested as a black box over its text responses; there is no gradient, no
perturbation norm, and no accuracy on a labelled set. Success here means the model
did something it was instructed not to — leaked a planted secret, or followed an
injected instruction that overrode its system prompt.
"""
