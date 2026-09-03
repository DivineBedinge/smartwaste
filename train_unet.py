# train_unet.py
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models
import os

def unet(input_size=(128,128,6)):
    inputs = layers.Input(input_size)
    # Encodeur
    c1 = layers.Conv2D(16, 3, activation='relu', padding='same')(inputs)
    c1 = layers.Conv2D(16, 3, activation='relu', padding='same')(c1)
    p1 = layers.MaxPooling2D(2)(c1)
    c2 = layers.Conv2D(32, 3, activation='relu', padding='same')(p1)
    c2 = layers.Conv2D(32, 3, activation='relu', padding='same')(c2)
    p2 = layers.MaxPooling2D(2)(c2)
    c3 = layers.Conv2D(64, 3, activation='relu', padding='same')(p2)
    c3 = layers.Conv2D(64, 3, activation='relu', padding='same')(c3)
    p3 = layers.MaxPooling2D(2)(c3)
    c4 = layers.Conv2D(128, 3, activation='relu', padding='same')(p3)
    c4 = layers.Conv2D(128, 3, activation='relu', padding='same')(c4)
    # Décodeur
    u3 = layers.UpSampling2D(2)(c4)
    u3 = layers.concatenate([u3, c3])
    c5 = layers.Conv2D(64, 3, activation='relu', padding='same')(u3)
    c5 = layers.Conv2D(64, 3, activation='relu', padding='same')(c5)
    u2 = layers.UpSampling2D(2)(c5)
    u2 = layers.concatenate([u2, c2])
    c6 = layers.Conv2D(32, 3, activation='relu', padding='same')(u2)
    c6 = layers.Conv2D(32, 3, activation='relu', padding='same')(c6)
    u1 = layers.UpSampling2D(2)(c6)
    u1 = layers.concatenate([u1, c1])
    c7 = layers.Conv2D(16, 3, activation='relu', padding='same')(u1)
    c7 = layers.Conv2D(16, 3, activation='relu', padding='same')(c7)
    outputs = layers.Conv2D(1, 1, activation='sigmoid')(c7)
    return models.Model(inputs, outputs)

def load_dataset(dataset_dir):
    images = []
    masks = []
    for f in os.listdir(os.path.join(dataset_dir, 'images')):
        if f.endswith('.npy'):
            img = np.load(os.path.join(dataset_dir, 'images', f))
            mask = np.load(os.path.join(dataset_dir, 'masks', f))
            images.append(img)
            masks.append(mask)
    images = np.array(images)
    masks = np.array(masks)
    images = np.transpose(images, (0, 2, 3, 1))  # (N, H, W, bands)
    masks = np.expand_dims(masks, axis=-1)
    return images, masks

if __name__ == "__main__":
    X, y = load_dataset('dataset')
    print(f"Forme des données : X={X.shape}, y={y.shape}")
    model = unet()
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy', tf.keras.metrics.MeanIoU(num_classes=2)])
    model.fit(X, y, batch_size=8, epochs=50, validation_split=0.2)
    model.save('modele_unet_satellite.h5')