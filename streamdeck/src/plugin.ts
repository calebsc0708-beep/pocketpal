import streamDeck from "@elgato/streamdeck";
import { PalKey } from "./actions/pal";

streamDeck.actions.registerAction(new PalKey());
streamDeck.connect();
