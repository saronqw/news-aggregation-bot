class Keyword(object):
    def __init__(self, coef, count, tag, university, score):
        self.coef = coef
        self.count = count
        self.tag = tag
        self.university = university
        self.score = score

    # def keyword_decoder(self):
    #     return Keyword(self['title'], self['description'], self.['link'], self['pub_date'])
