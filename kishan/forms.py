from django import forms

from kishan.models import ToolReview


class ToolReviewForm(forms.ModelForm):
    class Meta:
        model = ToolReview
        fields = ["rating", "comment"]

    def clean_comment(self):
        comment = self.cleaned_data.get("comment", "")
        if len(comment.strip()) < 10:
            raise forms.ValidationError(
                "Your review is too short. Please provide more details."
            )
        return comment
