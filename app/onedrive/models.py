class UploadInfo:
    def __init__(self,
                 uid: str,
                 drive_id: str,
                 filename: str,
                 file_path: str,
                 upload_path: str,
                 size: int,
                 created_date_time: str,
                 upload_url: str = None,
                 **kwargs):
        self.uid = uid
        self.drive_id = drive_id
        self.filename = filename
        self.file_path = file_path
        self.upload_path = upload_path
        self.size = size
        self.upload_url = upload_url
        self.created_date_time = created_date_time
        self.finished: int = kwargs.get('finished') or 0
        self.speed: int = kwargs.get('speed') or 0
        self.spend_time: float = kwargs.get('spend_time') or 0
        self.finished_date_time: str = kwargs.get('finished_date_time') or '---'
        self.valid = kwargs.get('valid') is None or kwargs.get('valid')
        self.error = kwargs.get('error')
        # self._commit必须放到最后赋值，而且赋值只能有一次。字典对象是可更改的
        self._commit = {}

    def __setattr__(self, key, value):
        if '_commit' not in self.__dict__.keys():
            # 初始化过程，要保证self._commit变量是最后一个赋值的
            super(UploadInfo, self).__setattr__(key, value)
            return
        assert key != '_commit'
        super(UploadInfo, self).__setattr__(key, value)
        # 这里不会触发__setattr__，因为对象没有变，而是对象内容改了
        self._commit.update({key: value})

    def commit(self):
        """
        对象初始化后，对对象的变量进行的一系列赋值操作
        :return:
        """
        res = self._commit.copy()
        self._commit.clear()
        return res

    def json(self):
        res = self.__dict__.copy()
        res.pop('_commit', None)
        return res
