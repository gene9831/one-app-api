class UploadInfo:
    FINISHED = 'finished'
    SPEED = 'speed'
    SPEND_TIME = 'spend_time'
    FINISHED_DT = 'finished_date_time'

    def __init__(self,
                 uid: str,
                 filename: str,
                 file_path: str,
                 upload_path: str,
                 size: int,
                 upload_url: str,
                 created_date_time: str,
                 **kwargs):
        self.uid = uid
        self.filename = filename
        self.file_path = file_path
        self.upload_path = upload_path
        self.size = size
        self.upload_url = upload_url
        self.created_date_time = created_date_time
        self.finished: int = kwargs.get(self.FINISHED) or 0
        self.speed: bool = kwargs.get(self.SPEED) or 0
        self.spend_time: float = kwargs.get(self.SPEND_TIME) or 0
        self.finished_date_time: str = kwargs.get(self.FINISHED_DT) or '---'

    def json(self):
        return self.__dict__.copy()
