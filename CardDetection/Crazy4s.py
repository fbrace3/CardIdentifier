# this file is the main file for the Crazy 4's game
# it uses the webcam to detect cards and show playable cards as well as wilds

import torch
import cv2
import numpy as np
from torchvision import transforms
import torch.nn as nn
from torchvision import transforms, models

def draw_rainbow_outline(frame, points, thickness=2):
    colors = [
        (255, 0, 0), (255, 165, 0), (255, 255, 0),
        (0, 128, 0), (0, 0, 255), (75, 0, 130), (238, 130, 238)
    ]
    for i, color in enumerate(colors):
        offset = i * thickness
        offset_points = points + offset
        cv2.polylines(frame, [offset_points], True, color, thickness)
        
def process_card(warped_image, model, class_names):
    preprocessed_image = preprocess_image(warped_image)
    with torch.no_grad():
        outputs = model(preprocessed_image)
        _, predicted = torch.max(outputs.data, 1)
        predicted_class = class_names[predicted.item()]
    return predicted_class

def is_playable(card, current_play_card):
    # Special cases
    if card == "Joker":
        return True
    if card == "Back" or current_play_card == "Back":
        return False

    # Ensure both card and current_play_card have an underscore before splitting
    if '_' in card and '_' in current_play_card:
        return card.split('_')[0] == current_play_card.split('_')[0] or card.split('_')[1] == current_play_card.split('_')[1]
    
    return False



# 3. Model Definition
class CardClassifier(nn.Module):
    def __init__(self):
        super(CardClassifier, self).__init__()
        resnet = models.resnet18(pretrained=True)
        resnet.conv1 = nn.Conv2d(1, 64, kernel_size=(7, 7), stride=(2, 2), padding=(3, 3), bias=False)  # Change to 1 input channel
        num_features = resnet.fc.in_features
        resnet.fc = nn.Linear(num_features, 54)  # 54 classes for 54 cards
        self.resnet = resnet

    def forward(self, x):
        return self.resnet(x)
    
# 1. Data Augmentation and Preprocessing
transform = transforms.Compose([
    transforms.Grayscale(num_output_channels=1),
    transforms.Resize((256, 256)),
    transforms.RandomVerticalFlip(),
    transforms.RandomHorizontalFlip(),
    transforms.ColorJitter(brightness=0.5, contrast=0.5),
    transforms.RandomAffine(degrees=0, translate=(0.1, 0.1)),
    transforms.RandomRotation(degrees=10),
    transforms.ToTensor(),
])


def preprocess_image(image, size=(256, 256)):
    transform = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Grayscale(num_output_channels=1),
        transforms.Resize(size),
        transforms.ToTensor(),
    ])
    image = transform(image)
    image = image.unsqueeze(0)  # Add batch dimension
    return image

def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxWidth = max(int(widthA), int(widthB))
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxHeight = max(int(heightA), int(heightB))
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped

def load_model(model_path):
    model = CardClassifier()  # Create an instance of your model
    state_dict = torch.load(model_path)  # Load the state dictionary
    model.load_state_dict(state_dict)  # Load the state dictionary into the model
    model.eval()
    return model


def main():
    model_path = "CardDetection\\best_model.pth"
    model = load_model(model_path)
    class_names = [
        'Ace_C', 'Two_C', 'Three_C', 'Four_C', 'Five_C',
        'Six_C', 'Seven_C', 'Eight_C', 'Nine_C', 'Ten_C',
        'Jack_C', 'Queen_C', 'King_C',
        'Ace_D', 'Two_D', 'Three_D', 'Four_D', 'Five_D',
        'Six_D', 'Seven_D', 'Eight_D', 'Nine_D', 'Ten_D',
        'Jack_D', 'Queen_D', 'King_D',
        'Ace_H', 'Two_H', 'Three_H', 'Four_H', 'Five_H',
        'Six_H', 'Seven_H', 'Eight_H', 'Nine_H', 'Ten_H',
        'Jack_H', 'Queen_H', 'King_H',
        'Ace_S', 'Two_S', 'Three_S', 'Four_S', 'Five_S',
        'Six_S', 'Seven_S', 'Eight_S', 'Nine_S', 'Ten_S',
        'Jack_S', 'Queen_S', 'King_S',
        'Joker', 'Back'
    ]

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    cv2.namedWindow('Card Detector', cv2.WINDOW_NORMAL)
    cv2.setWindowProperty('Card Detector', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred_frame = cv2.GaussianBlur(gray_frame, (9, 9), 0)
        adaptive_thresh = cv2.adaptiveThreshold(blurred_frame, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        contours, _ = cv2.findContours(adaptive_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected_cards = []

        for contour in contours:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            area = cv2.contourArea(contour)
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / float(h)

            if len(approx) == 4 and area > 4000 and 0.7 < aspect_ratio < 1.3:
                warped_image = four_point_transform(frame, approx.reshape(4, 2))
                predicted_class = process_card(warped_image, model, class_names)
                detected_cards.append((predicted_class, x, y, approx))

        # Sort detected cards by their x-coordinate
        detected_cards.sort(key=lambda card: card[1])

        # Determine the current play card and the player's hand
        if len(detected_cards) > 0:
            current_play_card = detected_cards[0][0]
            player_hand = detected_cards[1:]

            # Outline the current play card in yellow
            cv2.polylines(frame, [detected_cards[0][3]], True, (0, 255, 255), 2)
            cv2.putText(frame, current_play_card, (detected_cards[0][1], detected_cards[0][2] - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            # Add "Play Card Pile" text below the current play card
            cv2.putText(frame, "Play Card Pile", (detected_cards[0][1], detected_cards[0][2] + h + 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

            # Outline the player's hand cards in green or red based on playability
            for card in player_hand:
                color = (0, 255, 0) if is_playable(card[0], current_play_card) else (0, 0, 255)
                if "Four" in card[0]:
                    draw_rainbow_outline(frame, card[3], thickness=2)
                    color = (255, 0, 0)
                else:
                    cv2.polylines(frame, [card[3]], True, color, 2)
                cv2.putText(frame, card[0], (card[1], card[2] - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)


        cv2.imshow('Crazy 4\'s', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()