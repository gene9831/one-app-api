# -*- coding: utf-8 -*-
import inspect
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)


class Validator:
    def __init__(self):
        self.funcs = {}

    def register(self, name: str) -> Callable[..., Any]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.funcs[name] = func

            arg_spec = inspect.getfullargspec(func)
            args = arg_spec.args
            annotations = arg_spec.annotations

            if len(args) != 1:
                raise Exception(
                    'number of args should be 1. There are {} args: {}'.format(
                        len(args), args))

            if args[0] not in annotations.keys():
                raise Exception(
                    'the only arg must have type annotation to validate')

            if not isinstance(True, annotations.get('return')):
                logger.warning(
                    'type of return value in annotations could better be bool')

            setattr(func, 'validator_name', name)
            setattr(func, 'validator_args', args)
            setattr(func, 'validator_annotations', annotations)
            setattr(func, 'validator_value_type', annotations[args[0]])

            return func

        return decorator

    def validate(self, name: str, value: Any) -> bool:
        func = self.funcs.get(name)
        if func is not None:
            if not isinstance(value, getattr(func, 'validator_value_type')):
                return False
            return func(value)
        return False


validator = Validator()


@validator.register('onedrive.upload_chunk_size')
def upload_chunk_size(value: int) -> bool:
    return 5 <= value <= 60 and value % 5 == 0


@validator.register('onedrive.upload_threads_num')
def upload_threads_num(value: int) -> bool:
    return 0 < value <= 50


@validator.register('admin.auth_token_max_age')
def auth_token_max_age(value: int) -> bool:
    return 0 < value <= 30


to_do = [-5, 0, 5, 6, 9, 10, 59, 60, 61, 70]
if __name__ == '__main__':
    for i in to_do:
        print(i, validator.validate('onedrive.upload_chunk_size', i))
