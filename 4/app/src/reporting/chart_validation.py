import json
import numpy as np
from PIL import Image
from ..io_utils import sha256

class ChartValidationService:
    @staticmethod
    def validate_axis(ax,x,y):
        x=np.asarray(x,dtype=float); y=np.asarray(y,dtype=float)
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)): raise ValueError('Chart contains nonfinite coordinates')
        left,right=ax.get_xlim(); bottom,top=ax.get_ylim()
        eps=1e-8
        if x.size and (x.min()<left-eps or x.max()>right+eps): raise ValueError('Chart x data outside visible bounds')
        if y.size and (y.min()<bottom-eps or y.max()>top+eps): raise ValueError('Chart y data outside visible bounds')
        return dict(xlim=[left,right],ylim=[bottom,top],status='PASS')

    @staticmethod
    def image_geometry(path):
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            if min(im.size)<500: raise ValueError('Chart resolution too small')
            return dict(width=im.width,height=im.height,sha256=sha256(path),status='PASS')

    @staticmethod
    def visual_status(paths,review_file):
        if not review_file.exists(): return 'VISUAL_NOT_VERIFIED'
        rows=json.loads(review_file.read_text(encoding='utf-8'))
        approved={r['filename']:r for r in rows if r.get('status')=='PASS'}
        return 'PASS' if all(p.name in approved and approved[p.name].get('SHA256')==sha256(p) for p in paths) else 'VISUAL_NOT_VERIFIED'
